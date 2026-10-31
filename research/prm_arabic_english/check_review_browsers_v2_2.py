"""Real-browser review checks on public/temporary fixtures only; zero inference.

Uses an already installed matching browser/driver. No production input, approval,
model endpoint, download, training or scheduling mode exists.
"""
import argparse
import base64
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import tempfile
import review_browser_driver_v2_2 as controller

import diagnostic_assessment_ui_v2_2 as ui
import diagnostic_assessment_v2_1 as assessment
import diagnostic_design_review_v2_1 as design
import diagnostic_plan_v2_1 as plan
import recover_v2 as core
import resume_v2_local as legacy
from review_browser_driver_v2_2 import Browser, BrowserCheckError, installed
import test_diagnostic_assessment_v2_1 as fixtures

ROOT = Path(__file__).resolve().parents[2]
PROBE = Path(__file__).with_name('review_browser_probe_v2_2.js')
PACKAGE = ROOT / 'research/diagnostic24_design_review_v2_1'
ZIP_SHA = '1ae9f61d0c9d9179f6dca3b4143f92e3b4eaef8090dbd36881fb4ce44414dd89'


def require(value, message):
    if not value: raise BrowserCheckError(message)


def snapshot():
    release = plan.release()
    require(core.digest(release) == assessment.RELEASE_SHA, 'Frozen execution release changed')
    require(legacy.sha((PACKAGE/'ArabicPRM_Diagnostic24_Design_Review.zip').read_bytes()) == ZIP_SHA,
            'Original reviewer ZIP changed')
    return {str(p.relative_to(ROOT)): legacy.sha(p.read_bytes()) for p in
            [PACKAGE/'START_HERE.html', PACKAGE/'design_review_PENDING.json', PROBE, Path(__file__),
             Path(controller.__file__), Path(fixtures.__file__), Path(fixtures.__file__).with_name('test_diagnostic_v2_1.py'),
             Path(ui.__file__), ui.SCRIPT, *[Path(plan.__file__).parent/n for n in release['code_sha256']]]}


def fixture_path(temporary, name, data):
    p = temporary / name
    p.write_bytes(data)
    return p


def png_bytes(value):
    data = base64.b64decode(value, validate=True)
    require(len(data) > 5000 and data[:8] == b'\x89PNG\r\n\x1a\n' and data[12:16] == b'IHDR',
            'Real browser screenshot is missing/blank or invalid')
    width, height = struct.unpack('>II', data[16:24])
    require(width >= 300 and height >= 500, 'Browser screenshot dimensions are too small')
    return data, {'width': width, 'height': height, 'sha256': legacy.sha(data)}


def load(browser, temporary, name, raw):
    path = fixture_path(temporary, name+'.html', raw)
    browser.open_file(path)
    return browser.script(PROBE.read_text(encoding='utf-8'))


def saved(browser, expected):
    browser.script("document.getElementById('save').click();")
    browser.wait('window.__reviewProbe.captures.length === '+str(expected))
    return browser.script('return window.__reviewProbe.captures.at(-1);')


def screenshot(browser, output, name, *, width=1280, height=1000, label):
    browser.command('POST', '/window/rect', {'width': width, 'height': height})
    browser.script("""let mark=document.getElementById('browser-test-notice');
      if(!mark){mark=document.createElement('p');mark.id='browser-test-notice';document.body.prepend(mark);}
      mark.textContent=arguments[0];mark.style='background:#e8dcff;padding:12px;font-weight:bold';""", label)
    metrics = browser.script('return window.__reviewMetrics();')
    require(not metrics['unnamed_controls'], 'A reviewer control has no accessible name')
    require(not metrics['errors'], 'Browser script error: '+str(metrics['errors']))
    require(metrics['nonlocal_page_resources'] == 0, 'The fixture loaded an external resource')
    data, info = png_bytes(browser.command('GET', '/screenshot'))
    (output/(name+'.png')).write_bytes(data)
    return {'png': info, 'layout': metrics}


def csp_check(browser):
    result = browser.script("""const done=arguments[arguments.length-1];
      let blocked=false;document.addEventListener('securitypolicyviolation',e=>{if(e.effectiveDirective.startsWith('script-src'))blocked=true;},{once:true});
      const script=document.createElement('script');script.textContent='window.__untrustedReviewScriptRan=true';document.body.append(script);
      setTimeout(()=>done({blocked,ran:window.__untrustedReviewScriptRan===true}),100);""", asynchronous=True)
    require(result['blocked'] and not result['ran'], 'Browser did not enforce the original script CSP')
    return result


def check_design(browser, temporary, output):
    raw = (PACKAGE/'START_HERE.html').read_bytes()
    task = json.loads((PACKAGE/'design_review_PENDING.json').read_bytes())
    metrics = load(browser, temporary, 'design-source-only', raw)
    require(metrics['design_slots'] == 12 and metrics['source_problems'] == 7, 'Design sources disappeared in actual DOM')
    require(saved(browser, 1) == task, 'Default design export invented a human decision or metadata')
    browser.script("document.getElementById('decision').value='approve_design';document.getElementById('save').click();")
    require(browser.script('return window.__reviewProbe.captures.length;') == 1, 'Missing personal review allowed design approval')
    browser.script("document.getElementById('decision').value='pending';")
    path = fixture_path(temporary, 'design-draft.json', legacy.encoded(task))
    browser.resume_file(path)
    browser.wait("document.getElementById('status').textContent.startsWith('Loaded')")
    require(saved(browser, 2) == task, 'Native file resume changed the pending design task')
    design.validate_review(task, task)
    return {'scope': 'public source-only design fixture; no human review', 'csp': csp_check(browser),
            'screenshot': screenshot(browser, output, 'design-desktop', label='PUBLIC SOURCE-ONLY BROWSER TEST — HUMAN DESIGN REVIEW PENDING')}


def check_empty(browser, temporary, output):
    blind = fixtures.PublicFrozenAssessmentContractTests().blind()
    raw, task = ui.render(blind, 'human')
    metrics = load(browser, temporary, 'empty-public-blind', raw)
    require(metrics['candidates'] == 24 and metrics['pairs'] == 12, 'Not all planned observations are visible')
    require(browser.script("return [...document.querySelectorAll('[id^=decision-]')].every(e=>e.disabled&&e.value==='pending');"),
            'Unavailable candidates can acquire invented judgments')
    require(saved(browser, 1) == task, 'Empty human task invented metadata or assessments')
    assessment.validate_assessment(blind, task, 'human')
    desktop = screenshot(browser, output, 'empty-blind-desktop', label='PUBLIC SOURCE / EMPTY TEST FIXTURE — NOT LAPTOP EVIDENCE')
    mobile = screenshot(browser, output, 'empty-blind-mobile', width=390, height=900,
                        label='EMPTY TEST FIXTURE — NO GENERATED OUTPUTS OR HUMAN REVIEW')
    require(mobile['layout']['page_width'] <= mobile['layout']['viewport']+1, 'Blind form overflows a narrow viewport')
    return {'scope': 'real twelve source contexts; synthetic zero spec; all outputs absent', 'csp': csp_check(browser),
            'desktop': desktop, 'mobile': mobile, 'all24_missing_locked': True}


def check_synthetic(browser, temporary, output):
    fixture = fixtures.AssessmentFixture()
    fixture.setUp()
    try:
        blind = fixture.bundle(7, missing=(2,), english=(3,), transport=(4,))
        raw, task = ui.render(blind, 'ai')
        load(browser, temporary, 'synthetic-partial-blind', raw)
        original = copy.deepcopy(blind)
        require(browser.script("return document.querySelectorAll('.candidate').length;") == 24, 'Partial run dropped observations')
        for i, item in enumerate(blind['items']):
            for label, out in item['outputs'].items():
                value = browser.script("const e=document.getElementById(arguments[0]);return {disabled:e.disabled,faithful:[...e.options].some(o=>o.value==='faithful')};", 'decision-'+str(i)+'-'+label)
                require(value['disabled'] == (out['candidate'] is None), 'Missing output was unlocked')
                require(not value['faithful'] or out['mechanical_status'] == 'accepted', 'Hard rejection acquired a faithful option')
        i, label = next((i, label) for i,item in enumerate(blind['items']) for label,out in item['outputs'].items() if out['mechanical_status']=='accepted')
        key = str(i)+'-'+label
        require(saved(browser, 1) == task, 'Pending AI export changed source or invented judgments')
        browser.script("""const k=arguments[0],e=document.getElementById('decision-'+k);e.value='translation_error';e.dispatchEvent(new Event('change',{bubbles:true}));
          document.getElementById('severity-'+k).value='major';document.getElementById('category-'+k+'-operation').checked=true;
          document.getElementById('explanation-'+k).value='SYNTHETIC AUTOMATION FIXTURE — NOT A RESEARCH ASSESSMENT';
          document.getElementById('save').click();""", key)
        require(browser.script('return window.__reviewProbe.captures.length;') == 1, 'Missing identity/attestation permitted non-pending export')
        browser.script("document.getElementById('identity').value='SYNTHETIC BROWSER AI FIXTURE';document.getElementById('seconds').value='0';document.getElementById('blinding').checked=true;")
        first = saved(browser, 2)
        assessment.validate_assessment(blind, first, 'ai')
        require(first['measured_review_seconds'] == 0 and first['human_attested'] is False, 'AI/duration provenance changed')
        require(browser.script("return !document.getElementById('blinding').checked&&!document.getElementById('human').checked;"), 'Save retained stale attestations')
        browser.script("document.getElementById('explanation-'+arguments[0]).value='CHANGED SYNTHETIC FIXTURE';document.getElementById('save').click();", key)
        require(browser.script('return window.__reviewProbe.captures.length;') == 2, 'Changed work reused an old attestation')
        browser.script("document.getElementById('blinding').checked=true;")
        changed = saved(browser, 3)
        assessment.validate_assessment(blind, changed, 'ai')
        require(saved(browser, 4) == changed, 'Unchanged save invented a new clock/duration')
        path = fixture_path(temporary, 'synthetic-ai-draft.json', legacy.encoded(changed))
        browser.resume_file(path)
        browser.wait("document.getElementById('status').textContent.startsWith('Loaded')")
        require(saved(browser, 5) == changed, 'Native saved-file resume changed original metadata')
        bad = copy.deepcopy(changed); bad['assessor_kind'] = 'human'
        browser.resume_file(fixture_path(temporary, 'wrong-kind.json', legacy.encoded(bad)))
        browser.wait("document.getElementById('status').textContent.includes('Wrong source')")
        require(saved(browser, 6) == changed, 'Wrong-kind resume replaced original assessment')
        browser.script("document.getElementById('correction-'+arguments[0]).value='بطرح 8';document.getElementById('blinding').checked=true;", key)
        bad_correction = saved(browser, 7)
        try: assessment.validate_assessment(blind, bad_correction, 'ai')
        except ValueError: pass
        else: raise BrowserCheckError('Invalid numerical correction bypassed the unchanged Python validator')
        require(blind == original and plan.history_snapshot(fixture.repo) == fixture.before, 'Synthetic source/history changed')
        rtl = browser.script("return [...document.querySelectorAll('.candidate pre')].some(e=>/[\\u0600-\\u06ff]/.test(e.textContent)&&getComputedStyle(e).direction==='rtl');")
        require(rtl, 'Actual browser did not present Arabic candidates right-to-left')
        return {'scope': 'disposable synthetic partial-run and AI draft; no actual reviewer', 'all24_retained': True,
                'native_file_resume': True, 'fresh_attestations': True, 'zero_duration_preserved': True,
                'wrong_kind_blocked': True, 'invalid_correction_blocked_by_python': True,
                'csp': csp_check(browser), 'screenshot': screenshot(browser, output, 'synthetic-ai-desktop',
                    label='SYNTHETIC BROWSER FIXTURE — NOT REAL PILOT OUTPUTS OR QC')}
    finally:
        fixture.doCleanups()


def run(output, kind='auto'):
    output = core.safe_path(output)
    if ROOT == output or ROOT in output.parents:
        require(ROOT/'recovery_artifacts/diagnostic-browser-checks-v2.2' in output.parents,
                'Repository outputs must be isolated browser evidence, never protected paths')
    require(not output.exists(), 'Existing evidence is preserved; choose a fresh output directory')
    before = snapshot()
    kind, executable, driver = installed(kind)
    output.mkdir(parents=True)
    report = {'kind': 'offline_browser_test_evidence_v2_2', 'status': 'running', 'fixture_only': True,
              'human_qc_status': 'pending', 'training_eligible': False, 'generation_requests_authorized': 0,
              'checked_at_utc': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
              'source_snapshot_sha256': core.digest(before), 'screenshots_are_reviewer_approval': False}
    try:
        with tempfile.TemporaryDirectory(prefix='arabicprm-browser-fixture-') as name:
            temporary = Path(name)
            with Browser(kind, executable, driver, temporary) as browser:
                report['browser'] = {'name': browser.capabilities['browserName'], 'version': browser.capabilities['browserVersion'],
                                     'driver_sha256': legacy.sha(driver.read_bytes())}
                report['design'] = check_design(browser, temporary, output)
                report['empty_blind'] = check_empty(browser, temporary, output)
                report['synthetic_ai'] = check_synthetic(browser, temporary, output)
                report['webdriver_loopback_requests'] = browser.calls
        require(snapshot() == before, 'Public/frozen reviewer inputs changed')
        report['status'] = 'passed'
    except Exception as error:
        report.update(status='failed', error=str(error)); raise
    finally:
        (output/'browser-report.json').write_bytes(legacy.encoded(report))
        files = sorted(p for p in output.iterdir() if p.is_file())
        (output/'SHA256SUMS.txt').write_text(''.join(legacy.sha(p.read_bytes())+'  '+p.name+'\n' for p in files),encoding='ascii')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', choices=('auto','chrome','edge'), default='auto')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try: report = run(args.output_dir, args.browser)
    except (BrowserCheckError, ValueError, OSError, KeyError) as error:
        parser.exit(1, 'BROWSER CHECK BLOCKED: '+str(error)+'\n')
    print('REAL BROWSER CHECKS PASSED: '+json.dumps(report['browser'])+'; public/synthetic fixtures only; zero generation requests')


if __name__=='__main__': main()
