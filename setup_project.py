"""Local project setup. Never installs globally or starts a public server."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def run(command, cwd=ROOT):
    print('+ ' + ' '.join(map(str, command)), flush=True)
    subprocess.run([str(x) for x in command], cwd=cwd, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Install semantic retrieval and CPU GGUF generation, download the public Qwen model')
    args=parser.parse_args()
    if sys.version_info[:2] != (3,11):
        sys.exit('Use Python 3.11 for the documented setup (Windows: py -3.11 setup_project.py).')
    npm = shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:
        sys.exit('Install Node.js 22 LTS with npm, reopen the terminal, then rerun setup.')
    env=ROOT/'.venv'
    if not env.exists():
        venv.EnvBuilder(with_pip=True).create(env)
    python=env/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    run([python,'-m','pip','install','-r','requirements.txt','-r','requirements-dev.txt'])
    if args.full:
        print('Full setup downloads public model weights. No private logs are uploaded.',flush=True)
        run([python,'-m','pip','install','-r','requirements-semantic.txt'])
        run([python,'-m','pip','install','--only-binary=:all:','--extra-index-url',
             'https://abetlen.github.io/llama-cpp-python/whl/cpu','llama-cpp-python==0.3.36'])
        run([python,'-m','pip','install','huggingface-hub>=1,<2'])
        run([python,'download_model.py'])
    run([npm,'ci'],ROOT/'frontend')
    run([npm,'test'],ROOT/'frontend')
    run([npm,'run','build'],ROOT/'frontend')
    run([python,'-m','pytest','-q'])
    print('\nSetup complete. See RUN_WINDOWS.md. Default start: .venv\\Scripts\\python.exe run.py' if os.name=='nt' else '\nSetup complete. Start: .venv/bin/python run.py')


if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError:
        sys.exit('Setup stopped at the failing command above. Nothing is running. See troubleshooting in RUN_WINDOWS.md.')
