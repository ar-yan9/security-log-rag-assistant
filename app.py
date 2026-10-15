"""Loopback-only local log evidence API and CLI. No hosted generation service."""
import argparse
from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
from threading import RLock
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from retrieval import EvidenceIndex, read_records
from generation import LocalGenerator, answer

DEFAULT_FILE = str(Path(__file__).with_name('demo.jsonl'))
_index = None
_generator = None
_lock = RLock()


@asynccontextmanager
async def lifespan(application):
    yield
    global _index, _generator
    with _lock:
        for resource in (_generator, _index):
            if resource is not None:
                resource.close()
        _index = _generator = None


app = FastAPI(title='Security Log Evidence Assistant', lifespan=lifespan)
from fastapi.middleware.trustedhost import TrustedHostMiddleware
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])


@app.middleware('http')
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response


class SearchRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    limit: int = Field(default=3, ge=1, le=10)


def make_index(path, mode):
    records = read_records(path)
    if mode == 'semantic':
        from semantic import SemanticIndex
        return SemanticIndex(records)
    if mode != 'lexical':
        raise ValueError('RETRIEVAL_MODE must be lexical or semantic')
    return EvidenceIndex(records)


def get_index():
    global _index
    with _lock:
        if _index is None:
            _index = make_index(os.getenv('SECURITY_LOG_FILE', DEFAULT_FILE),
                                os.getenv('RETRIEVAL_MODE', 'lexical'))
        return _index


def get_generator():
    global _generator
    path = os.getenv('LOCAL_GGUF_MODEL')
    if not path:
        return None
    with _lock:
        if _generator is None:
            _generator = LocalGenerator(path)
        return _generator


@app.get('/health')
def health():
    # Liveness only. Does not claim corpus/model readiness before lazy loading.
    return {'status': 'alive', 'retrieval_mode': os.getenv('RETRIEVAL_MODE', 'lexical'),
            'llm_configured': bool(os.getenv('LOCAL_GGUF_MODEL')),
            'llm_enabled': _generator is not None, 'corpus_loaded': _index is not None,
            'sample_corpus': os.getenv('SECURITY_LOG_FILE', DEFAULT_FILE) == DEFAULT_FILE}


def guarded_search(request, generate=False):
    try:
        with _lock:
            index = get_index()
            return answer(index, get_generator(), request.question, request.limit) if generate else index.search(request.question, request.limit)
    except (ValueError, UnicodeError) as exc:
        raise HTTPException(status_code=400, detail='Invalid local configuration, corpus, or query') from exc
    except (OSError, ImportError, RuntimeError) as exc:
        raise HTTPException(status_code=503, detail='Local corpus, dependency, or model unavailable') from exc


@app.post('/search')
def search(request: SearchRequest):
    return guarded_search(request)


@app.post('/ask')
def ask(request: SearchRequest):
    return guarded_search(request, generate=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question')
    parser.add_argument('--semantic', action='store_true', help='BGE + Qdrant; first run downloads a public embedding model')
    parser.add_argument('--model', help='Local Qwen-compatible GGUF path; enables extractive RAG')
    parser.add_argument('--file', default=DEFAULT_FILE)
    args = parser.parse_args(argv)
    index = generator = None
    try:
        index = make_index(args.file, 'semantic' if args.semantic else 'lexical')
        if args.model:
            generator = LocalGenerator(args.model)
            result = answer(index, generator, args.question)
        else:
            result = index.search(args.question)
        print(json.dumps(result, indent=2))
        status = result['status']
        if status in ('generation_rejected', 'generation_unavailable'):
            return 2
        return 0 if status in ('answer_ready', 'evidence_found') else 1
    except (OSError, ValueError, UnicodeError, ImportError, RuntimeError):
        print('Error: local corpus, dependency, model, or query unavailable/invalid')
        return 2
    finally:
        for resource in (generator, index):
            if resource is not None:
                resource.close()


if __name__ == '__main__':
    raise SystemExit(main())

# Production build uses one loopback origin. Development Vite proxy uses the
# same /api prefix. Keep API routes before the static mount.
app.add_api_route('/api/health', health, methods=['GET'])
app.add_api_route('/api/search', search, methods=['POST'])
app.add_api_route('/api/ask', ask, methods=['POST'])
_frontend = Path(__file__).parent / 'frontend' / 'dist'
if _frontend.is_dir():
    from fastapi.staticfiles import StaticFiles
    app.mount('/', StaticFiles(directory=_frontend, html=True), name='frontend')
