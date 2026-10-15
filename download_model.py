"""Download a fixed public Qwen model; no token or account needed."""
from pathlib import Path
from huggingface_hub import hf_hub_download

if __name__ == '__main__':
    path=hf_hub_download('Qwen/Qwen2.5-0.5B-Instruct-GGUF',
                         'qwen2.5-0.5b-instruct-q4_k_m.gguf',
                         revision='9217f5db79a29953eb74d5343926648285ec7e67',
                         local_dir=Path(__file__).parent/'models')
    print(path)
