"""Exercise deployment control flow without touching the host Docker daemon."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'deploy-local.sh'
MOCK = '''#!/usr/bin/env python3
import os, sys, json
from pathlib import Path
a=sys.argv[1:]
with open(os.environ['CALLS'], 'a') as f: f.write(json.dumps(a)+'\\n')
if a[:2]==['container','inspect']:
    sys.exit(1 if a[-1].endswith('-previous') else 0)
if a[0]=='inspect':
    fmt=a[2]
    if 'local-deploy' in fmt: print('true' if os.environ['MODE']=='managed' else '')
    elif 'compose.service' in fmt: print('other' if os.environ['MODE']=='foreign' else 'devsecops-app')
    elif 'Networks' in fmt: print('project_devsecops')
    elif 'Running' in fmt: print('true')
    elif 'Health' in fmt: print('unhealthy' if os.environ['MODE']=='unhealthy' else 'healthy')
if a[0]=='cp' and os.environ['MODE']=='copy_failure': sys.exit(1)
if a[0]=='run' and '-i' in a: sys.stdin.buffer.read()
if a[0]=='run' and '-d' in a:
    data=Path(a[a.index('--env-file')+1]).read_bytes()
    assert b'\\r' not in data and not data.startswith(b'\\xef\\xbb\\xbf')
'''

class DeploymentTests(unittest.TestCase):
    def run_case(self, mode, port='5001'):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            docker=root/'docker'; docker.write_text(MOCK); docker.chmod(0o700)
            secret=root/'secret'; secret.write_bytes(b'\xef\xbb\xbfAPP_API_KEY='+b'a'*64+b'\r\nLOG_LEVEL=INFO\r\n')
            calls=root/'calls'
            env=dict(os.environ, PATH=folder+':'+os.environ['PATH'], TMPDIR=folder,
                     APP_IMAGE='test-image', APP_CONTAINER='devsecops-local-app',
                     APP_VOLUME='devsecops-local-data', APP_PORT=port,
                     APP_ENV_FILE=str(secret), CALLS=str(calls), MODE=mode)
            result=subprocess.run(['bash',str(SCRIPT)],env=env,capture_output=True)
            import json
            commands=[json.loads(line) for line in calls.read_text().splitlines()]
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['calls','docker','secret'])
            return result, commands

    def test_compose_takeover(self):
        result, calls=self.run_case('compose')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['cp','devsecops-app-previous:/tmp/users.db','-'],calls)
        run=next(c for c in calls if c[:2]==['run','-d'])
        self.assertIn('5001:5000',run)
        self.assertIn('project_devsecops',run)
        self.assertIn('devsecops-app-data:/data',run)
        self.assertIn(['rm','devsecops-app-previous'],calls)

    def test_managed_replacement(self):
        result,calls=self.run_case('managed')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertFalse(any(c[0]=='cp' for c in calls))

    def test_local_5002(self):
        result,calls=self.run_case('managed','5002')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn(['rename','devsecops-local-app','devsecops-local-app-previous'],calls)

    def test_rollback(self):
        for mode in ('copy_failure','unhealthy'):
            with self.subTest(mode=mode):
                result,calls=self.run_case(mode)
                self.assertNotEqual(result.returncode,0)
                self.assertIn(['rename','devsecops-app-previous','devsecops-app'],calls)
                self.assertIn(['start','devsecops-app'],calls)

    def test_foreign_container_rejected(self):
        result,calls=self.run_case('foreign')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(any(c[0] in ('stop','rename','rm') for c in calls))

if __name__ == '__main__':
    unittest.main()
