"""Installed-browser test controller. Only its own loopback WebDriver, never a model.

No Selenium Manager, downloads, shared browser profile, login or scheduling.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import build_opener, HTTPRedirectHandler, ProxyHandler, Request


class BrowserCheckError(RuntimeError):
    pass


def installed(kind='auto', *, windows=None, environ=None, which=None):
    windows = os.name == 'nt' if windows is None else windows
    environ = os.environ if environ is None else environ
    which = shutil.which if which is None else which
    kind = ('edge' if windows else 'chrome') if kind == 'auto' else kind
    if kind not in ('chrome', 'edge'):
        raise ValueError('Only installed Chrome or Edge is allowed')
    browsers = [which(n) for n in (('google-chrome', 'chromium', 'chromium-browser', 'chrome')
                                  if kind == 'chrome' else ('microsoft-edge', 'msedge'))]
    drivers = [which('chromedriver' if kind == 'chrome' else 'msedgedriver')]
    executable = ('chromedriver' if kind == 'chrome' else 'msedgedriver') + ('.exe' if windows else '')
    driver_dir = environ.get('CHROMEWEBDRIVER' if kind == 'chrome' else 'EDGEWEBDRIVER')
    if driver_dir:
        drivers.append(str(Path(driver_dir) / executable))
    if windows:
        for key in ('ProgramFiles', 'ProgramFiles(x86)'):
            if environ.get(key):
                suffix = ('Google/Chrome/Application/chrome.exe' if kind == 'chrome'
                          else 'Microsoft/Edge/Application/msedge.exe')
                browsers.append(str(Path(environ[key]) / suffix))
    browser = next((Path(p) for p in browsers if p and Path(p).is_file()), None)
    driver = next((Path(p) for p in drivers if p and Path(p).is_file()), None)
    if browser is None or driver is None:
        raise BrowserCheckError('Installed '+kind+' and matching WebDriver required; nothing will be downloaded')
    return kind, browser.resolve(), driver.resolve()


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BrowserCheckError('WebDriver redirects are forbidden')


class Browser:
    def __init__(self, kind, executable, driver, temporary):
        self.kind, self.executable, self.driver = kind, Path(executable), Path(driver)
        self.temporary = Path(temporary)
        self.process = self.session = self.log = None
        self.calls = 0
        # Proxy bypass applies solely to the controller's newly allocated loopback port.
        # No Internet destination or caller-supplied URL can use this client.
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def request(self, method, path, payload=None, timeout=20):
        if not path.startswith('/') or '://' in path or '\\' in path or self.port == 11434:
            raise BrowserCheckError('Only the owned WebDriver route is permitted')
        data = None if payload is None else json.dumps(payload).encode('utf-8')
        req = Request('http://127.0.0.1:'+str(self.port)+path, data=data, method=method,
                      headers={'Content-Type': 'application/json; charset=utf-8'})
        self.calls += 1
        try:
            with self.opener.open(req, timeout=timeout) as response:
                document = json.loads(response.read().decode('utf-8'))
        except HTTPError as error:
            raise BrowserCheckError('WebDriver '+str(error.code)+': '+error.read().decode('utf-8')[:2000]) from None
        value = document.get('value')
        if isinstance(value, dict) and value.get('error'):
            raise BrowserCheckError(str(value))
        return value

    def __enter__(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0)); self.port = sock.getsockname()[1]
        if self.port == 11434:
            raise BrowserCheckError('Model port forbidden')
        self.log = (self.temporary / 'webdriver.log').open('wb')
        try:
            self.process = subprocess.Popen([str(self.driver), '--port='+str(self.port), '--allowed-ips=127.0.0.1'],
                                            stdout=self.log, stderr=subprocess.STDOUT)
            deadline = time.monotonic()+15
            while True:
                if self.process.poll() is not None:
                    raise BrowserCheckError('Installed WebDriver exited during startup')
                try:
                    if self.request('GET', '/status', timeout=1).get('ready'):
                        break
                except (URLError, TimeoutError, ConnectionError):
                    pass
                if time.monotonic() >= deadline:
                    raise BrowserCheckError('Installed WebDriver startup timed out')
                time.sleep(.1)
            args = ['--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
                    '--disable-background-networking', '--disable-component-update', '--disable-sync',
                    '--disable-extensions', '--disable-dev-shm-usage',
                    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE localhost',
                    '--user-data-dir='+str(self.temporary / 'fresh-profile')]
            if hasattr(os, 'geteuid') and os.geteuid() == 0:
                args.append('--no-sandbox')  # Root-only disposable CI/test profile.
            vendor = 'goog:chromeOptions' if self.kind == 'chrome' else 'ms:edgeOptions'
            capabilities = {'browserName': 'chrome' if self.kind == 'chrome' else 'MicrosoftEdge',
                            vendor: {'binary': str(self.executable), 'args': args}}
            value = self.request('POST', '/session', {'capabilities': {'alwaysMatch': capabilities}})
            self.session = value['sessionId']; self.capabilities = value['capabilities']
            self.command('POST', '/timeouts', {'script': 15000, 'pageLoad': 20000, 'implicit': 0})
            return self
        except BaseException as error:
            try: self.__exit__(type(error), error, error.__traceback__)
            except Exception: pass  # Preserve the original startup failure after cleanup.
            raise

    def command(self, method, route, payload=None):
        return self.request(method, '/session/'+quote(self.session, safe='')+route, payload)

    def script(self, text, *args, asynchronous=False):
        return self.command('POST', '/execute/'+('async' if asynchronous else 'sync'),
                            {'script': text, 'args': list(args)})

    def open_file(self, path):
        path = Path(path).resolve(strict=True)
        if path.suffix != '.html' or self.temporary.resolve() not in path.parents:
            raise BrowserCheckError('Only a disposable local HTML fixture may be opened')
        self.command('POST', '/url', {'url': path.as_uri()})

    def resume_file(self, path):
        path = Path(path).resolve(strict=True)
        if path.suffix != '.json' or self.temporary.resolve() not in path.parents:
            raise BrowserCheckError('Only a disposable fixture draft may be resumed')
        element = self.command('POST', '/element', {'using': 'css selector', 'value': '#resume'})
        element_id = element['element-6066-11e4-a52e-4f735466cecf']
        self.command('POST', '/element/'+quote(element_id, safe='')+'/value', {'text': str(path)})

    def wait(self, expression, timeout=10):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            if self.script('return Boolean('+expression+');'):
                return
            time.sleep(.05)
        raise BrowserCheckError('Browser fixture condition timed out: '+expression)

    def __exit__(self, *_):
        try:
            if self.session:
                self.command('DELETE', '')
        finally:
            if self.process:
                self.process.terminate()
                try: self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=5)
            if self.log: self.log.close()
