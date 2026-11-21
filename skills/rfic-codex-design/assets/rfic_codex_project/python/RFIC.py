import os
import subprocess
from pathlib import Path
import time
import re
import json
import math
from itertools import product
import select
import tempfile

os.chdir(os.path.dirname(os.path.abspath(__file__)))
DEPLOY_FILE = Path(__file__).resolve().parent.parent / "json" / "deploy.json"
with DEPLOY_FILE.open("r", encoding="utf-8") as f:
    deploy = json.load(f)

home_dir = deploy["virtuoso_dir"]
tech = deploy["tech"]
mos_name = deploy["mos_name"]
lib_name = deploy["lib_name"]
project_name = deploy["project_name"]
project_dir = Path(home_dir) / project_name
show_gui = deploy.get("show_gui", False)
if not isinstance(show_gui, bool):
    raise ValueError("show_gui must be a JSON boolean")
gui_display = deploy.get("gui_display", os.environ.get("DISPLAY", ":0"))
lib_path = deploy.get("lib_path", str(Path(home_dir) / lib_name))
symbol_lib = deploy.get("symbol_lib", "rfic_codex_symbol")
project_symbol_path = project_dir / symbol_lib
symbol_lib_path = deploy.get("symbol_lib_path", str(
    project_symbol_path if project_symbol_path.is_dir() else Path(home_dir) / symbol_lib
))
model_path = deploy["model_path"]
model_type = deploy["model_type"]
setup_file_path = deploy["setup_file_path"]
simulation_path = deploy["simulation_path"]
emx_work_addr = deploy["emx_work_addr"]
proc_file_addr = deploy["proc_file_addr"]
emx_addr = deploy["emx_addr"]

pcell_dir = project_dir / "pcell"
ocean_dir = project_dir / "ocean"
output_dir = project_dir / "output"
skill_path = pcell_dir / "RFIC.il"
ocean_path = str(ocean_dir / "RFIC.ocn")
ade_state_path = ocean_dir / "ade_state"
run_path = str(pcell_dir / "run.il")
pcell_dir.mkdir(parents=True, exist_ok=True)

command_path = str(pcell_dir / "RFIC_command.il")
done_path = str(pcell_dir / "RFIC_command.done")
pid_path = str(pcell_dir / "RFIC_virtuoso.pid")
display_state_path = pcell_dir / "RFIC_display.json"
_virtual_display_process = None
_virtuoso_process = None


def _process_identity(pid):
    try:
        return Path(f"/proc/{int(pid)}/stat").read_text().rsplit(") ", 1)[1].split()[19]
    except (OSError, ValueError, IndexError):
        return None


def _stop_virtual_display():
    global _virtual_display_process
    if display_state_path.exists():
        state = json.loads(display_state_path.read_text())
        pid = state.get("xvfb_pid")
        if pid and state.get("xvfb_start") and _process_identity(pid) == state["xvfb_start"]:
            os.kill(pid, 15)
            if _virtual_display_process is not None:
                _virtual_display_process.wait(timeout=10)
        display_state_path.unlink()
    _virtual_display_process = None


def _display_environment():
    global _virtual_display_process
    environment = os.environ.copy()
    if show_gui:
        if not isinstance(gui_display, str) or not gui_display:
            raise ValueError("gui_display must name an accessible X display")
        environment["DISPLAY"] = gui_display
        state = dict(show_gui=True, display=gui_display)
    else:
        read_fd, write_fd = os.pipe()
        try:
            with tempfile.TemporaryFile() as errors:
                _virtual_display_process = subprocess.Popen(
                    ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "2048x1152x24", "-nolisten", "tcp"],
                    pass_fds=(write_fd,), stdout=subprocess.DEVNULL, stderr=errors)
                os.close(write_fd)
                write_fd = None
                ready, _, _ = select.select([read_fd], [], [], 30)
                number = os.read(read_fd, 64).decode().strip() if ready else ""
                if not number.isdigit() or _virtual_display_process.poll() is not None:
                    if _virtual_display_process.poll() is None:
                        _virtual_display_process.terminate()
                    _virtual_display_process.wait(timeout=10)
                    errors.seek(0)
                    raise RuntimeError("Cannot start Xvfb: " + errors.read().decode(errors="replace"))
            environment["DISPLAY"] = ":" + number
            state = dict(show_gui=False, display=environment["DISPLAY"],
                         xvfb_pid=_virtual_display_process.pid,
                         xvfb_start=_process_identity(_virtual_display_process.pid))
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
    display_state_path.write_text(json.dumps(state))
    return environment


def _skill_string(value):
    return json.dumps(str(value), ensure_ascii=False)


def create_lib():
    return _submit_skill(f"create_lib({_skill_string(lib_name)} {_skill_string(lib_path)} {_skill_string(tech)})")


def register_symbolLib():
    return _submit_skill(f"RFIC_register_symbol_lib({_skill_string(symbol_lib)} {_skill_string(symbol_lib_path)})")


def _session_running():
    try:
        with open(pid_path) as pid_file:
            pid = int(pid_file.read().strip())
        if display_state_path.exists():
            state = json.loads(display_state_path.read_text())
            if state.get("virtuoso_pid") != pid or state.get("virtuoso_start") != _process_identity(pid):
                return False
        os.kill(pid, 0)
        if os.path.isdir("/proc"):
            with open(f"/proc/{pid}/status") as status_file:
                if re.search(r"^State:\s+[ZX]\b", status_file.read(), re.M):
                    return False
        return True
    except (OSError, ValueError):
        return False

def _ensure_virtuoso():
    global _virtuoso_process
    if _session_running():
        if not display_state_path.exists():
            raise RuntimeError("Existing session has no display metadata; close it before migration")
        state = json.loads(display_state_path.read_text())
        if state["show_gui"] != show_gui or (show_gui and state["display"] != gui_display):
            raise RuntimeError("Close the current design before changing display configuration")
        return
    _stop_virtual_display()
    run_content = f'''
    RFIC_emx_config_path={_skill_string(Path(emx_addr).parent.parent / "virtuoso_ui/emxinterface/emxskill/emxconfig.il")}
    load({_skill_string(skill_path)})
    RFIC_start_session({_skill_string(command_path)} {_skill_string(done_path)})
    '''
    with open(run_path, "w") as run:
        run.write(run_content)
    environment = _display_environment()
    try:
        process = subprocess.Popen(["virtuoso", "-restore", run_path], cwd=home_dir, env=environment)
    except BaseException:
        _stop_virtual_display()
        raise
    _virtuoso_process = process
    state = json.loads(display_state_path.read_text())
    state.update(virtuoso_pid=process.pid, virtuoso_start=_process_identity(process.pid))
    display_state_path.write_text(json.dumps(state))
    with open(pid_path, "w") as pid_file:
        pid_file.write(str(process.pid))
    time.sleep(8)

def _submit_skill(content, timeout=600, completion_delay=0):
    _ensure_virtuoso()
    if os.path.exists(done_path):
        os.remove(done_path)
    content = f'''load({_skill_string(skill_path)})
RFIC_start_session({_skill_string(command_path)} {_skill_string(done_path)})
RFIC_execute_command(lambda(nil
{content}
) {_skill_string(done_path)} {completion_delay})
'''
    temporary_path = command_path + ".tmp"
    with open(temporary_path, "w") as command:
        command.write(content)
    os.replace(temporary_path, command_path)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _session_running():
            raise RuntimeError("Virtuoso exited before completing the command")
        if os.path.exists(done_path):
            with open(done_path) as completed:
                status = completed.read().strip()
            if status not in ("0", "1"):
                time.sleep(0.05)
                continue
            os.remove(done_path)
            if status != "0":
                raise RuntimeError("Virtuoso command failed; inspect CIW")
            return 0
        time.sleep(1)
    raise TimeoutError("Virtuoso command timed out")

def close_virtuoso():
    if not _session_running():
        _stop_virtual_display()
        return
    _submit_skill('hiRegTimer("exit()" 30)', timeout=15)
    deadline = time.monotonic() + 30
    while _session_running():
        if _virtuoso_process is not None:
            _virtuoso_process.poll()
        if time.monotonic() >= deadline:
            raise TimeoutError("Virtuoso did not exit; check the desktop for a save or confirmation dialog")
        time.sleep(0.5)
    Path(pid_path).unlink(missing_ok=True)
    if _virtuoso_process is not None:
        _virtuoso_process.wait(timeout=5)
    _stop_virtual_display()


def _run_ocean_visible(path_ocean, cell_name):
    with open(path_ocean) as ocean:
        source = ocean.read()
    configuration, extraction = source.split('run()', 1)
    if re.search(r'\bforeach\s*\(', configuration):
        raise ValueError("Use _run_ade_parametric for parameter sweeps")
    extraction = extraction[:extraction.rfind('\nif(numberp')]
    tokens = re.sub(r'"(?:\\.|[^"\\])*"|;[^\n]*', '', extraction)
    if tokens.count(')') == tokens.count('(') + 1 and extraction.rstrip().endswith(')'):
        extraction = extraction.rstrip()[:-1]
    _prepare_ade(configuration, extraction, cell_name)
    completion_path = str(pcell_dir / "RFIC_ade_point.done")
    if os.path.exists(completion_path):
        os.remove(completion_path)
    run_content = f'''
    procedure(RFIC_ade_point_finished(session status)
        let((p)
            printf("RFIC ADE point completed: %L\\n" status)
            p = outfile({_skill_string(completion_path)})
            fprintf(p "%L" status)
            close(p)))
    asiRegCallBackOnSimComp(RFIC_ade_asi 'RFIC_ade_point_finished)
    asiRegCallBackOnSimCompForDist(RFIC_ade_asi 'RFIC_ade_point_finished)
    sevNetlistAndRun(RFIC_ade_session)
    '''
    _submit_skill(run_content, timeout=60)
    deadline = time.time() + 3600
    while not os.path.exists(completion_path):
        if time.time() > deadline:
            raise TimeoutError("ADE simulation timed out; windows left open")
        time.sleep(1)
    with open(completion_path) as completed:
        if completed.read().strip() not in ('t', '0'):
            raise RuntimeError("ADE simulation failed; windows left open")
    _submit_skill("asiUnRegCallBackOnSimComp(RFIC_ade_asi 'RFIC_ade_point_finished)\nasiUnRegCallBackOnSimCompForDist(RFIC_ade_asi 'RFIC_ade_point_finished)", timeout=30)
    result = extraction.replace('openResults(resultsDir())', 'openResults(asiGetPsfDir(RFIC_ade_asi))')
    _submit_skill(result + '\nsevEvaluateAndPlotExpressions(RFIC_ade_session)', timeout=60)

def _prepare_ade(configuration, extraction, cell_name, additional_outputs=None):
    configuration = configuration[configuration.index('simulator('):]
    analyses = []
    for match in re.finditer(r"analysis\('([A-Za-z0-9_]+)", configuration):
        depth, quoted, escaped, stop = 1, False, False, match.end()
        while depth:
            char = configuration[stop]
            if escaped:
                escaped = False
            elif char == '\\' and quoted:
                escaped = True
            elif char == '"':
                quoted = not quoted
            elif not quoted:
                depth += (char == '(') - (char == ')')
            stop += 1
        arguments = configuration[match.end():stop - 1]
        options = list(re.finditer(r'\?(\w+)\s+', arguments))
        entries = []
        for index, option in enumerate(options):
            stop = options[index + 1].start() if index + 1 < len(options) else len(arguments)
            value = arguments[option.end():stop].strip()
            entries.append(f"list('{option.group(1)} {value})")
        analyses.append(f"RFIC_configure_analysis('{match.group(1)} list({' '.join(entries)}))")
    model = re.search(r'modelFile\(\s*\'\("([^"]+)"\s+"([^"]+)"\)', configuration)
    model_setup = f"asiSetEnvOptionVal(RFIC_ade_asi 'modelFiles list(list({json.dumps(model.group(1))} {json.dumps(model.group(2))})))" if model else ''
    output_expressions = {}
    for match in re.finditer(r'^\s*(Idd|Pout|Pin|Iq|DE|Gain|Zin_real|Zin_imag|Sdd11|Freq)\s*=\s*(.+)$', extraction, re.M):
        expression = match.group(2).strip()
        output_expressions[match.group(1)] = expression
    metric_names = list(output_expressions)
    metric_assignments = '\n'.join(f'{name} = {expression}' for name, expression in output_expressions.items())
    outputs = f'procedure(RFIC_metric_values() let(({" ".join(metric_names)})\n{metric_assignments}\nlist({" ".join(metric_names)})))\n'
    outputs += '''procedure(RFIC_set_output_expression(name expression)
        sevAddExpression(RFIC_ade_session name expression)
        let((index)
            index=0
            foreach(output RFIC_ade_session->outputs
                when(output->name == name
                    sevTableSelectRows(RFIC_ade_session->outForm->outListBox index)
                    sevSetPropertyForSelectedOuts(RFIC_ade_session "expression" car(linereadstring(expression))))
                index=index+1)))\n'''
    outputs += '\n'.join(f'RFIC_set_output_expression({json.dumps(name)} {json.dumps(f"nth({index} RFIC_metric_values())")})' for index, name in enumerate(metric_names) if name not in ('Freq', 'Sdd11'))
    for name, expression in (additional_outputs or {}).items():
        outputs += f'\nRFIC_set_output_expression({json.dumps(name)} {json.dumps(expression)})'
    _submit_skill(configuration + '\nRFIC_source_asi=asiGetCurrentSession()', timeout=60)
    state_name = f"RFIC_visible_{time.time_ns()}"
    opening = f'''
    RFIC_awv_windows_before = awvGetWindowList()
    when(boundp('RFIC_ade_session) && boundp('RFIC_ade_window) && windowp(RFIC_ade_window)
        RFIC_ade_session->saveQuery=nil
        RFIC_close_confirmations_active=t
        hiRegTimer("RFIC_close_confirmation_windows(50)" 1)
        errset(sevQuit(RFIC_ade_session) t)
        when(windowp(RFIC_ade_window) hiCloseWindow(RFIC_ade_window))
        RFIC_close_confirmations_active=nil)
    RFIC_ade_schematic_cell = list({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic")
    RFIC_ade_window = deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "r")
    sevStartSession(?lib {_skill_string(lib_name)} ?cell {_skill_string(cell_name)} ?view "schematic" ?schematic RFIC_ade_window)
    RFIC_ade_session = sevSession(RFIC_ade_window)
    RFIC_ade_session->saveQuery=nil
    unless(RFIC_ade_session error("RFIC: ADE session was not created"))
    RFIC_ade_asi = sevEnvironment(RFIC_ade_session)
    asiSetDesignVarList(RFIC_ade_asi asiGetDesignVarList(RFIC_source_asi))
    procedure(RFIC_configure_analysis(name settings)
        let((analysis fields)
            analysis = asiGetAnalysis(RFIC_ade_asi name)
            fields = mapcar('asiGetName asiGetAnalysisFieldList(analysis))
            foreach(setting settings
                if(member(car(setting) fields) then
                    asiSetAnalysisFieldVal(analysis car(setting) cadr(setting))
                else
                    asiSetAnalysisOptionVal(analysis car(setting) cadr(setting))))
            asiEnableAnalysis(analysis)
            unless(asiIsAnalysisEnabled(analysis) error("RFIC: analysis not enabled"))))
    {chr(10).join(analyses)}
    {model_setup}
    asiSetEnvOptionVal(RFIC_ade_asi 'analysisOrder list("dc" "hb" "sp"))
    asiSetKeepList(RFIC_ade_asi asiGetKeepList(RFIC_source_asi))
    sevSetSimDataDir(RFIC_ade_session {_skill_string(simulation_path)})
    {outputs}
    procedure(RFIC_enable_ade_plots()
        let((index)
            index=0
            foreach(output RFIC_ade_session->outputs
                when(output->expression
                    sevSetTableItem(RFIC_ade_session->outForm->outListBox index 2 "true"))
                index=index+1)))
    RFIC_enable_ade_plots()
    unless(asiSaveState(RFIC_ade_asi ?name "{state_name}" ?option 'dir ?stateDir {_skill_string(ade_state_path)}) error("RFIC: ADE state save failed"))
    unless(asiLoadState(RFIC_ade_asi ?name "{state_name}" ?option 'dir ?stateDir {_skill_string(ade_state_path)}) error("RFIC: ADE state load failed"))
    '''
    _submit_skill(opening, timeout=60)
    _submit_skill('RFIC_ade_asi=sevEnvironment(RFIC_ade_session)\nRFIC_enable_ade_plots()\nforeach(o RFIC_ade_session->outputs when(o->expression && !o->plot error("RFIC: output Plot flags are not enabled")))', timeout=30)

def _close_ade_windows():
    close_path = str(pcell_dir / "RFIC_ade_closed.done")
    if os.path.exists(close_path):
        os.remove(close_path)
    closing = f'''
    RFIC_ade_ui_window = RFIC_ade_session->window
    RFIC_ade_plot_windows = setof(w awvGetWindowList() !member(w RFIC_awv_windows_before))
    RFIC_ade_schematic_windows = setof(w hiGetWindowList()
        w->cellView &&
        w->cellView->libName == car(RFIC_ade_schematic_cell) &&
        w->cellView->cellName == cadr(RFIC_ade_schematic_cell) &&
        w->cellView->viewName == caddr(RFIC_ade_schematic_cell))
    procedure(RFIC_finish_ade_windows()
        let((errors p)
            errors=nil
            RFIC_close_confirmations_active=t
            hiRegTimer("RFIC_close_confirmation_windows(50)" 1)
            foreach(w RFIC_ade_plot_windows
                unless(errset(awvCloseWindow(w) t) errors=cons("plot" errors)))
            when(boundp('RFIC_param_window) && windowp(RFIC_param_window)
                unless(errset(apaCloseWindowCB(RFIC_param_window) t) errors=cons("parametric" errors)))
            when(windowp(RFIC_ade_ui_window)
                RFIC_ade_session->saveQuery=nil
                unless(errset(sevQuit(RFIC_ade_session) t) errors=cons("ADE" errors)))
            foreach(w RFIC_ade_schematic_windows
                when(windowp(w)
                    unless(errset(hiCloseWindow(w) t) errors=cons("schematic" errors))))
            RFIC_close_confirmation_windows()
            RFIC_close_confirmations_active=nil
            when(windowp(RFIC_ade_ui_window) || setof(w RFIC_ade_schematic_windows windowp(w))
                errors=cons("window remained open" errors))
            printf("RFIC ADE cleanup finished at %s; errors=%L\\n" getCurrentTime() errors)
            p=outfile({_skill_string(close_path)})
            fprintf(p "%d" if(errors 1 0))
            close(p)))
    printf("RFIC ADE cleanup scheduled at %s; delay=5s\\n" getCurrentTime())
    hiRegTimer("RFIC_finish_ade_windows()" 50)
    '''
    _submit_skill(closing, timeout=30)
    deadline = time.time() + 40
    while not os.path.exists(close_path):
        if time.time() > deadline:
            raise TimeoutError("ADE window cleanup timed out")
        time.sleep(0.5)
    with open(close_path) as completed:
        if completed.read().strip() != "0":
            raise RuntimeError("ADE window cleanup failed; inspect CIW")

def _run_ade_parametric(path_ocean, cell_name, sweep_parameters=None, additional_outputs=None):
    with open(path_ocean) as ocean:
        source = ocean.read()
    if sweep_parameters is None:
        sweep = re.search(r"foreach\(val '\((.*?)\)\s*desVar\(\"pin\" val\)\s*run\(\)", source, re.S)
        if not sweep:
            raise ValueError("Pin sweep definition is missing from the OCEAN script")
        configuration = source[:sweep.start()]
        extraction = source[sweep.end():source.rfind('\nif(numberp')]
        extraction = extraction.rsplit('\n)', 1)[0]
        axes = [("pin", -30.0, 30.0, 31)]
    else:
        axes = sweep_parameters
        configuration, extraction = source.split("run()", 1)
        extraction = extraction[:extraction.rfind('\nif(numberp')]
    _prepare_ade(configuration, extraction, cell_name, additional_outputs=additional_outputs)
    completion_path = str(pcell_dir / "RFIC_parametric.done")
    if os.path.exists(completion_path):
        os.remove(completion_path)
    setup = f'''
    RFIC_result_windows_before = hiGetWindowList()
    sevParametricTool(RFIC_ade_session)
    RFIC_param_window = hiGetCurrentWindow()
    RFIC_param_tool = eval(RFIC_param_window->hiForm)
    '''
    _submit_skill(setup, timeout=60)
    total_points = math.prod(axis[3] for axis in axes)
    for row, (name, lower, upper, count) in enumerate(axes):
        if row:
            _submit_skill('_apaAddRow(RFIC_param_tool->parametricForm)', timeout=30)
        step = (upper - lower) / (count - 1)
        for column, value in [(0, name), (3, "From/To"), (6, "Linear Steps"), (4, f"{lower:.15g}"), (5, f"{upper:.15g}"), (7, f"{step:.15g}")]:
            _submit_skill(f'_apaSetData(RFIC_param_tool->parametricForm {row} {column} "{value}")', timeout=30)
    start = f'''
    RFIC_enable_ade_plots()
    foreach(o RFIC_ade_session->outputs
        when(o->expression && !o->plot error("RFIC: output Plot flag lost before sweep")))
    RFIC_parametric_confirmation_active=t
    hiRegTimer("RFIC_confirm_parametric_points(300)" 1)
    apaStartCB(RFIC_param_window ?all t)
    unless(RFIC_param_tool->args->total_points == {total_points}
        apaStopCB(RFIC_param_window)
        error("RFIC: unexpected number of parametric sweep points"))
    '''
    sweep_started_at = time.time()
    _submit_skill(start, timeout=60)
    deadline = time.time() + 3600
    while not os.path.exists(completion_path):
        if time.time() > deadline:
            raise TimeoutError("ADE parametric sweep timed out; windows left open")
        _submit_skill(f'when(RFIC_param_tool->args->runObject->context == \'closed let((p) p=outfile({_skill_string(completion_path)}) fprintf(p "0") close(p)))', timeout=30)
        time.sleep(1)
    with open(completion_path) as completed:
        if completed.read().strip() != "0":
            raise RuntimeError("ADE parametric sweep failed; windows left open")
    _submit_skill('RFIC_parametric_confirmation_active=nil', timeout=30)
    if sweep_parameters is None:
        _finish_ade_parametric(extraction)
    else:
        _finish_ade_load_sweep(extraction, axes, sweep_started_at)


def _finish_ade_load_sweep(extraction, axes, sweep_started_at=None):
    metadata_path = str(pcell_dir / "RFIC_parametric_directory.txt")
    _submit_skill(f'let((p) p=outfile({_skill_string(metadata_path)}) fprintf(p "%s" RFIC_param_tool->args->dataDir) close(p))', timeout=30)
    with open(metadata_path) as metadata:
        data_dir = Path(metadata.read().strip())
    expected = list(product(*[[lower + index * (upper - lower) / (count - 1) for index in range(count)] for _, lower, upper, count in axes]))
    results = {}
    for psf in data_dir.rglob("psf"):
        if not psf.is_dir():
            continue
        values = {}
        for part in psf.relative_to(data_dir).parts:
            for component in part.split(","):
                for name, _, _, _ in axes:
                    if component.startswith(name + "="):
                        values[name] = float(component[len(name) + 1:])
        if len(values) != len(axes):
            continue
        actual = tuple(values[name] for name, _, _, _ in axes)
        matches = [key for key in expected if all(math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-8) for a, b in zip(key, actual))]
        if not matches:
            continue
        if sweep_started_at is not None:
            log_file = psf / "logFile"
            if not log_file.is_file() or log_file.stat().st_mtime < sweep_started_at:
                continue
        if len(matches) != 1 or matches[0] in results:
            raise RuntimeError("Unexpected or duplicate load-pull result directory")
        results[matches[0]] = psf
    if len(results) != len(expected):
        raise RuntimeError(f"Incomplete load-pull sweep: {len(results)}/{len(expected)} result directories")
    report_path = re.search(r'outfile\("([^"]+)"\s+"a"\)', extraction).group(1)
    with open(report_path) as report:
        header = report.readline()
    with open(report_path, "w") as report:
        report.write(header)
    collection = []
    for key in expected:
        result = extraction.replace('openResults(resultsDir())', f'openResults({json.dumps(str(results[key]))})')
        for (name, _, _, _), value in zip(axes, key):
            result = re.sub(rf'(?m)^(\s*{re.escape(name)}\s*=)\s*VAR\("{re.escape(name)}"\)', lambda match: f"{match.group(1)} {value!r}", result)
        collection.append(result)
    _submit_skill('\n'.join(collection), timeout=max(120, len(expected) * 2))
    with open(report_path) as report:
        rows = [line.split() for line in report.readlines()[1:] if line.strip()]
    if len(rows) != len(expected):
        raise RuntimeError("Load-pull sweep report has missing rows")
    for row, key in zip(rows, expected):
        if len(row) != 7 or not all(math.isfinite(float(value)) for value in row):
            raise RuntimeError("Invalid load-pull sweep data")
        if not all(abs(float(value) - target) <= 0.011 for value, target in zip(row[:2], key)):
            raise RuntimeError("Load-pull report coordinates do not match the sweep")
    _submit_skill('RFIC_enable_ade_plots()\nsevEvaluateAndPlotExpressions(RFIC_ade_session)', timeout=60)

def _finish_ade_parametric(extraction):
    report = re.search(r'outfile\("([^"]+)"\s+"a"\)', extraction).group(1)
    with open(report) as existing:
        header = existing.readline()
    with open(report, "w") as output:
        output.write(header)
    collection = []
    for point in range(-30, 31, 2):
        result = extraction.replace('openResults(resultsDir())', f'openResults(strcat(RFIC_param_tool->args->dataDir "/pin={point}/psf"))')
        result = result.replace('Pin = VAR("pin")', f'Pin = {float(point)}')
        collection.append(result)
    _submit_skill('\n'.join(collection), timeout=120)
    with open(report) as output:
        rows = [line.split() for line in output.readlines()[1:] if line.strip()]
    if len(rows) != 31 or [float(row[0]) for row in rows] != list(range(-30, 31, 2)):
        raise RuntimeError("ADE sweep result verification failed; windows left open")
    _submit_skill('RFIC_enable_ade_plots()\nsevEvaluateAndPlotExpressions(RFIC_ade_session)', timeout=60)

def generate_schematic(value,generation_code,transformer_name):
    if deploy and value == 3:
        create_lib()
    wizard_args = (tech, mos_name, lib_name, generation_code, transformer_name, model_path, setup_file_path)
    wizard_command = f"fill_wizard({int(value)} {' '.join(map(_skill_string, wizard_args))})"
    run_content = f'''
    load({_skill_string(skill_path)})
    hiRegTimer("open_wizard()" 10)
    hiRegTimer({_skill_string(wizard_command)} 20)
    hiRegTimer("close_log_window()" 30)
    '''
    result = _submit_skill(run_content, timeout=180, completion_delay=80)
    _submit_skill('when(boundp(\'Passive_tool_APP_FieldForm) hiFormCancel(Passive_tool_APP_FieldForm))', timeout=30)
    return result

def start_emx(transformer_name,Freq_low,Freq_up):
    Path(emx_work_addr).mkdir(parents=True, exist_ok=True)
    result_path = str(Path(emx_work_addr) / f"{lib_name}_{transformer_name}.work" / f"{transformer_name}.s4p")
    status_path = str(pcell_dir / "RFIC_emx.done")
    if os.path.exists(status_path):
        os.remove(status_path)
    start_time = time.time()
    run_content = f'''
    deOpenCellView({_skill_string(lib_name)} {_skill_string(transformer_name)} "layout" "maskLayout" nil "a")
    RFIC_emx_window = hiGetCurrentWindow()
    EMX_path = {_skill_string(Path(emx_addr).parent)}
    EMX_process_path = {_skill_string(Path(proc_file_addr).parent)}
    EMX_process_name = {_skill_string(Path(proc_file_addr).name)}
    EMX_EMX_opts = "-e 1 -t 1 -v 0.5 --3d=* --verbose=0 -l 2 --quasistatic --parallel=0 --simultaneous-frequencies=0 --recommended-memory"
    bgui = create_EMX_gui(nil nil)
    bgui->Start->value = {Freq_low}e9
    bgui->Stop->value = {Freq_up}e9
    bgui->Step->value = "2e8"
    bgui->Signals->value = "pri_p pri_m sec_p sec_m"
    bgui->Grounds->value = ""
    bgui->Process->value = {_skill_string(Path(proc_file_addr).name)}
    bgui->advanced_gui->Work_dir->value = {_skill_string(emx_work_addr)}
    RFIC_emx_form = bgui
    RFIC_emx_started = nil
    procedure(RFIC_close_emx_windows()
        let((status_file)
            foreach(job EMX_jobs_by_id(RFIC_emx_form)
                when(job->log_viewer && windowp(job->log_viewer)
                    hiCloseWindow(job->log_viewer)))
            hiFormCancel(RFIC_emx_form)
            when(windowp(RFIC_emx_window) hiCloseWindow(RFIC_emx_window))
            status_file=outfile({_skill_string(status_path)})
            fprintf(status_file "0")
            close(status_file)))
    procedure(RFIC_check_emx_completion()
        let((jobs finished success status_file)
            jobs = EMX_jobs_by_id(RFIC_emx_form)
            finished = RFIC_emx_started && jobs && RFIC_emx_form->active_jobs == 0 && null(RFIC_emx_form->pending_jobs)
            success = t
            foreach(job jobs
                update_EMX_status(job)
                unless(numberp(job->status) && job->status == 0 success = nil))
            if(finished then
                if(success then
                    hiRegTimer("RFIC_close_emx_windows()" 50)
                else
                    status_file = outfile({_skill_string(status_path)})
                    fprintf(status_file "1")
                    close(status_file))
            else
                hiRegTimer("RFIC_check_emx_completion()" 10))
        ))
    hiRegTimer("hiDisplayForm(RFIC_emx_form)" 1)
    procedure(RFIC_start_emx_ready()
        hiiSetCurrentForm(RFIC_emx_form->hiFormSym)
        if(hiGetCurrentForm() == RFIC_emx_form then
            start_EMX()
            RFIC_emx_started = t
        else
            error("RFIC: EMX form context not available")))
    hiRegTimer("RFIC_start_emx_ready()" 10)
    hiRegTimer("RFIC_check_emx_completion()" 20)
    '''
    _submit_skill(run_content, timeout=60)
    print("EMX simulation started in Virtuoso.")
    deadline = time.time() + 3600
    while time.time() < deadline:
        if os.path.exists(status_path):
            with open(status_path) as status_file:
                status = status_file.read().strip()
            if status == "0" and os.path.exists(result_path) and os.path.getmtime(result_path) >= start_time:
                print("EMX simulation complete.")
                return result_path
            raise RuntimeError("EMX simulation failed; windows left open for inspection")
        time.sleep(2)
    raise TimeoutError("EMX simulation timed out")

def copy_schematic(cell_name):
    if deploy:
        create_lib()
    run_content = f'''
    load({_skill_string(skill_path)})
    copy_schematic({_skill_string(cell_name)} {_skill_string(lib_name)})
    RFIC_Delete({_skill_string(lib_name)} {_skill_string(cell_name)} 3.2)
    cv = dbOpenCellViewByType({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "" "a")
    place_PA_instance_and_wire(cv)
    edit_property(cv)
    generate_V(cv)
    deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "a")
    '''
    return _submit_skill(run_content, timeout=60)

def generate_testbench(cell_name):
    if deploy:
        register_symbolLib()
    run_content = f'''
    load({_skill_string(skill_path)})
    RFIC_Delete({_skill_string(lib_name)} {_skill_string(cell_name)} 3.2)
    cv = dbOpenCellViewByType({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "" "a")
    place_in_transformer(cv 4 3 {_skill_string(symbol_lib)})
    place_out_transformer(cv 4 1.5 {_skill_string(symbol_lib)})
    deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "a")
    '''
    return _submit_skill(run_content, timeout=60)

def start_ADE_simulation(cell_name,generation_code,R,L,Cp_in,Cs_in,Cp_out,Cs_out,s4p_path_in,s4p_path_out):
    parts = generation_code.split("/")
    freq = float(parts[1])
    vdd = float(parts[2])
    mul = int(parts[5])
    nof = int(parts[6])
    mul2 = int(parts[7])
    nof2 = int(parts[8])
    vbias = float(parts[9])

    path_ocean =ocean_path
    dir_ocean = os.path.dirname(path_ocean) 
    path_output = str(output_dir / f"RFIC_{cell_name}" / f"RFIC_{cell_name}.txt")
    dir_output = os.path.dirname(path_output)
    os.makedirs(dir_ocean,exist_ok=True)
    os.makedirs(dir_output,exist_ok=True)

    with open(path_output,"w") as report:
        report.write("Pin(dBm) Pout(dBm) Gain(dB) Iq(mA) Idd(mA) DE(%) S11 S22 Kf B1f\n")

    ocn_content = f"""
deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "r")
simulator( 'spectre )
design(  {_skill_string(lib_name)} {_skill_string(cell_name)} "schematic")
resultsDir( {_skill_string(Path(simulation_path) / cell_name / "spectre" / "schematic")} )
modelFile(
        '({_skill_string(model_path)} {_skill_string(model_type)})
)
analysis('hb ?HBTranMode "Yes"  ?tstab "50p"  ?autoharms "yes"
                ?autotstab ""  ?autosteady "yes"  ?oversample list("1")  ?fundfreqs list("(Freq)")
                ?maxharms list("5")  )
analysis('dc ?saveOppoint t  ?param "temp"  )
analysis('sp ?ports list("/PORT0" "/PORT1")  ?start "1G"  ?stop "80G"  )
desVar(   "Freq" {freq}G    )
desVar(   "Mul" {mul}      )
desVar(   "Mul2" {mul2}      )
desVar(   "NoF" {nof}      )
desVar(   "NoF2" {nof2}     )
desVar(   "pin" 10      )
desVar(   "Vbias" {vbias}  )
desVar(   "Vdd" {vdd}     )
desVar(   "R" {R}       )
desVar(   "L" {L}       )
desVar(   "Cp_in" {Cp_in}       )
desVar(   "Cs_in" {Cs_in}       )
desVar(   "Cp_out" {Cp_out}     )
desVar(   "Cs_out" {Cs_out}     )
desVar(   "s4p_path_in" "\\\"{s4p_path_in}\\\""       )
desVar(   "s4p_path_out" "\\\"{s4p_path_out}\\\""     )
envOption(
        'analysisOrder  list("dc" "hb" "sp")
)
save( 'i "/Vdd/PLUS" )
temp( 27 )
foreach(val '(-30 -25 -20 -15 -10 -5 2 4 6 8 10 12 14 16 18 20 22 24 26 28 30 )
    desVar("pin" val)
    run()
    fout = outfile("{path_output}" "a")
        if(openResults(resultsDir()) then
            Idd = value(mag(i("/Vdd/PLUS" ?result "hb_fd")) 0)
            Pout = dbm(harmonic(pvr('hb "/OUT" "/vssa" 50.0) 1))
            Pin = VAR("pin")
            Iq = (- pv("Vdd" "i" ?result "dcOpInfo"))
            DE = (100 * (pow(10 ((Pout - 30) / 10)) / (VAR("Vdd") * Idd)))
            Gain = (Pout - Pin)
            S11 = ymax(mag(spm('sp 1 1)))
            S22 = ymax(mag(spm('sp 2 2)))
            Kf = ymin(kf(sp(1 1 ?result "sp") sp(1 2 ?result "sp") sp(2 1 ?result "sp") sp(2 2 ?result "sp")))
            B1f = ymin(b1f(sp(1 1 ?result "sp") sp(1 2 ?result "sp") sp(2 1 ?result "sp") sp(2 2 ?result "sp")))
            fprintf(fout "%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\n" Pin Pout Gain Iq*1000 Idd*1000 DE S11 S22 Kf B1f)
        )
        close(fout)
)
if(numberp(Pin) && numberp(Gain) && numberp(DE) then
    printf("RFIC simulation complete\n")
else
    error("RFIC simulation failed")
)
"""
    with open(path_ocean,"w")as ocn:
            ocn.write(ocn_content)

    print("仿真中…")

    _run_ade_parametric(path_ocean, cell_name, additional_outputs={
        "Kf": 'kf(sp(1 1 ?result "sp") sp(1 2 ?result "sp") sp(2 1 ?result "sp") sp(2 2 ?result "sp"))',
        "B1f": 'b1f(sp(1 1 ?result "sp") sp(1 2 ?result "sp") sp(2 1 ?result "sp") sp(2 2 ?result "sp"))',
        "S11_max": "ymax(mag(spm('sp 1 1)))",
        "S22_max": "ymax(mag(spm('sp 2 2)))",
    })
    print("仿真完成")
    _close_ade_windows()

def Zin_ADE_simulation(cell_name,generation_code,R,L,ZLoad_real,ZLoad_imag):
    parts = generation_code.split("/")
    freq = float(parts[1])
    vdd = float(parts[2])
    mul = int(parts[5])
    nof = int(parts[6])
    mul2 = int(parts[7])
    nof2 = int(parts[8])
    vbias = float(parts[9])

    path_ocean =ocean_path
    dir_ocean = os.path.dirname(path_ocean) 
    path_output = str(output_dir / f"RFIC_{cell_name}" / f"RFIC_{cell_name}_Zin.txt")
    dir_output = os.path.dirname(path_output)
    os.makedirs(dir_ocean,exist_ok=True)
    os.makedirs(dir_output,exist_ok=True)

    with open(path_output,"w") as report:
        report.write("Zin_real\t\tZin_imag\t\n")

    ocn_content = f"""
deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "r")
simulator( 'spectre )
design(  {_skill_string(lib_name)} {_skill_string(cell_name)} "schematic")
resultsDir( {_skill_string(Path(simulation_path) / cell_name / "spectre" / "schematic")} )
modelFile(
        '({_skill_string(model_path)} {_skill_string(model_type)})
)
analysis('sp ?ports list("/PORT1" "/PORT2")  ?start "Freq*0.5"  ?stop "Freq*1.5"
                ?lin "100"  )
desVar(   "Freq" {freq}G    )
desVar(   "Mul" {mul}      )
desVar(   "Mul2" {mul2}      )
desVar(   "NoF" {nof}      )
desVar(   "NoF2" {nof2}     )
desVar(   "Vbias" {vbias}  )
desVar(   "Vdd" {vdd}     )
desVar(   "R" {R}       )
desVar(   "L" {L}       )
desVar(   "ZLoad_real" {ZLoad_real}     )
desVar(   "ZLoad_imag" {ZLoad_imag}     )
envOption(
        'analysisOrder  list("sp")
)
save( 'i "/Vdd/PLUS" )
temp( 27 )
run()
    fout = outfile("{path_output}" "a")
        if(openResults(resultsDir()) then
        Sdd11 = (((aaSP("/PORT1" "/PORT1") - aaSP("/PORT1" "/PORT2") - aaSP("/PORT2" "/PORT1")) + aaSP("/PORT2" "/PORT2")) / 2)
        Freq = VAR("Freq")
        Zin_imag = value(imag(((50 * (1 + Sdd11)) / (1 - Sdd11))) Freq)
        Zin_real = value(real(((50 * (1 + Sdd11)) / (1 - Sdd11))) Freq)
        fprintf(fout "%.2f\\t\\t%.2f\\t\\t\\n" Zin_real Zin_imag)
        )
        close(fout)
)
if(numberp(Zin_real) then
    printf("RFIC Zin simulation complete\n")
else
    error("RFIC Zin simulation failed")
)
"""
    with open(path_ocean,"w")as ocn:
            ocn.write(ocn_content)

    print("仿真中…")

    _run_ocean_visible(path_ocean, cell_name)
    print("仿真完成")
    _close_ade_windows()

def measure_Zin(cell_name):
    run_content = f'''
    load({_skill_string(skill_path)})
    RFIC_Delete({_skill_string(lib_name)} {_skill_string(cell_name)} 3.2)
    cv = dbOpenCellViewByType({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "" "a")
    measure_Zin(cv)
    port3(cv)
    deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "a")
    '''
    return _submit_skill(run_content, timeout=60)

def load_pull(cell_name):
    if deploy:
        register_symbolLib()
    path_output = str(output_dir / f"RFIC_{cell_name}" / f"RFIC_{cell_name}_load_pull.txt")
    dir_output = os.path.dirname(path_output)
    os.makedirs(dir_output,exist_ok=True) 
    with open(path_output,"w") as report:
        report.write("ZLoad_real (Ohm)\t\tZLoad_imag(Ohm)\tPout (dBm)\tGain (dBm)\tIq (mA)\t\tIdd (mA)\t\tDE(%)\n")

    run_content = f'''
    load({_skill_string(skill_path)})
    RFIC_Delete({_skill_string(lib_name)} {_skill_string(cell_name)} 3.2)
    cv = dbOpenCellViewByType({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "" "a")
    place_in_transformer(cv 4 3 {_skill_string(symbol_lib)})
    port3(cv)
    deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "a")
    '''
    return _submit_skill(run_content, timeout=60)

def _write_load_pull_ocean(cell_name,generation_code,R,L,pin,ZLoad_real,ZLoad_imag,Cp_in,Cs_in,s4p_path_in,sweep_pin=False):
    path_output = str(output_dir / f"RFIC_{cell_name}" / f"RFIC_{cell_name}_load_pull.txt")
    run_statement = "run()"
    sweep_end = ""
    output_format = "%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\n"
    output_values = "ZLoad_real ZLoad_imag Pout Gain Iq*1000 Idd*1000 DE"
    pout_expression = "dbm((0.5 * ((real(Vout) * real(Iout)) + (imag(Vout) * imag(Iout)))))"
    if sweep_pin:
        path_output = str(output_dir / f"RFIC_{cell_name}" / f"RFIC_{cell_name}_load_pull_pin.txt")
        os.makedirs(os.path.dirname(path_output), exist_ok=True)
        with open(path_output, "w") as report:
            report.write("Pin(dBm) Pout(dBm) Gain(dB) Iq(mA) Idd(mA) DE(%)\n")
        pins = " ".join(str(point) for point in range(-30, 31, 2))
        run_statement = f'foreach(val \'({pins})\n desVar("pin" val)\nrun()'
        sweep_end = ")"
        output_format = "%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\t%.2f\\n"
        output_values = "Pin Pout Gain Iq*1000 Idd*1000 DE"
    pout_expression = pout_expression.replace("Vout", "harmonic((vh('hb \"/outp\") - vh('hb \"/outm\")) 1)").replace("Iout", "harmonic(ih('hb \"/PORT3/PLUS\") 1)")
    parts = generation_code.split("/")
    freq = float(parts[1])
    vdd = float(parts[2])
    mul = int(parts[5])
    nof = int(parts[6])
    mul2 = int(parts[7])
    nof2 = int(parts[8])
    vbias = float(parts[9])

    path_ocean =ocean_path
    dir_ocean = os.path.dirname(path_ocean) 
    os.makedirs(dir_ocean,exist_ok=True)

    ocn_content = f"""
deOpenCellView({_skill_string(lib_name)} {_skill_string(cell_name)} "schematic" "schematic" nil "r")
simulator( 'spectre )
design(  {_skill_string(lib_name)} {_skill_string(cell_name)} "schematic")
resultsDir( {_skill_string(Path(simulation_path) / cell_name / "spectre" / "schematic")} )
modelFile(
        '({_skill_string(model_path)} {_skill_string(model_type)})
)
analysis('dc ?saveOppoint t  )
analysis('hb ?autoharms ""  ?autotstab "yes"  ?oversample list("2")
                ?fundfreqs list("(Freq)")  ?maxharms list("5")  ?freqdivide ""  ?lsspDisplayHarmonic ""
                ?displayHarmonic ""  )
desVar(   "Freq" {freq}G    )
desVar(   "Mul" {mul}      )
desVar(   "Mul2" {mul2}      )
desVar(   "NoF" {nof}      )
desVar(   "NoF2" {nof2}     )
desVar(   "pin" {pin}      )
desVar(   "Vbias" {vbias}  )
desVar(   "Vdd" {vdd}     )
desVar(   "R" {R}       )
desVar(   "L" {L}       )
desVar(   "ZLoad_real" {ZLoad_real}     )
desVar(   "ZLoad_imag" {ZLoad_imag}     )
desVar(   "Cp_in" {Cp_in}       )
desVar(   "Cs_in" {Cs_in}       )
desVar(   "s4p_path_in" "\\\"{s4p_path_in}\\\""       )
envOption(
        'analysisOrder  list("hb" "dc")
)
save( 'i "/Vdd/PLUS" )
temp( 27 )
{run_statement}
    fout = outfile("{path_output}" "a")
        if(openResults(resultsDir()) then
        Iout = harmonic(ih('hb "/PORT3/PLUS") 1)
        Vout = harmonic((vh('hb "/outp") - vh('hb "/outm")) 1)
        Pout = {pout_expression}
        Idd = (- real(harmonic(i("/Vdd/PLUS" ?result "hb_fd") 0)))
        Pin = VAR("pin")
        ZLoad_real = VAR("ZLoad_real")
        ZLoad_imag =VAR("ZLoad_imag")
        Gain = (Pout - Pin)
        DE = (100 * (pow(10 ((Pout - 30) / 10)) / (VAR("Vdd") * Idd)))
        Iq = (- pv("Vdd" "i" ?result "dcOpInfo"))
        fprintf(fout "{output_format}" {output_values})
        )
        close(fout)
{sweep_end}
if(numberp(Pin) && numberp(Gain) && numberp(DE) then
    printf("RFIC load-pull simulation complete\n")
else
    error("RFIC load-pull simulation failed")
)
"""
    with open(path_ocean,"w")as ocn:
            ocn.write(ocn_content)

    return path_ocean, path_output


def load_pull_simulation(cell_name,generation_code,R,L,pin,ZLoad_real,ZLoad_imag,Cp_in,Cs_in,s4p_path_in,sweep_pin=False):
    path_ocean, path_output = _write_load_pull_ocean(cell_name,generation_code,R,L,pin,ZLoad_real,ZLoad_imag,Cp_in,Cs_in,s4p_path_in,sweep_pin)
    print("仿真中…")

    if sweep_pin:
        try:
            _run_ade_parametric(path_ocean, cell_name)
        finally:
            _close_ade_windows()
    else:
        _run_ocean_visible(path_ocean, cell_name)
    print("仿真完成")
    return path_output


def load_pull_parametric_simulation(cell_name,generation_code,R,L,pin,ZLoad_real_min,ZLoad_real_max,ZLoad_real_points,ZLoad_imag_min,ZLoad_imag_max,ZLoad_imag_points,Cp_in,Cs_in,s4p_path_in):
    axes = []
    for name, lower, upper, count in [("ZLoad_real", ZLoad_real_min, ZLoad_real_max, ZLoad_real_points), ("ZLoad_imag", ZLoad_imag_min, ZLoad_imag_max, ZLoad_imag_points)]:
        if isinstance(count, bool) or not isinstance(count, int) or count < 2:
            raise ValueError(f"{name}: sweep point count must be an integer of at least 2")
        lower, upper = float(lower), float(upper)
        if not math.isfinite(lower) or not math.isfinite(upper) or lower >= upper:
            raise ValueError(f"{name}: sweep bounds must be finite and lower < upper")
        if name == "ZLoad_real" and lower <= 0:
            raise ValueError("Load resistance must be positive")
        axes.append((name, lower, upper, count))
    if not math.isfinite(float(pin)):
        raise ValueError("Pin must be finite")
    path_ocean, single_report = _write_load_pull_ocean(cell_name,generation_code,R,L,pin,axes[0][1],axes[1][1],Cp_in,Cs_in,s4p_path_in)
    path_output = str(output_dir / f"RFIC_{cell_name}" / f"RFIC_{cell_name}_load_pull_sweep.txt")
    os.makedirs(os.path.dirname(path_output), exist_ok=True)
    with open(path_output, "w") as report:
        report.write("ZLoad_real(Ohm) ZLoad_imag(Ohm) Pout(dBm) Gain(dB) Iq(mA) Idd(mA) DE(%)\n")
    with open(path_ocean) as ocean:
        source = ocean.read()
    with open(path_ocean, "w") as ocean:
        ocean.write(source.replace(f'outfile("{single_report}" "a")', f'outfile("{path_output}" "a")'))
    print(f"Load-pull parametric sweep: Pin={pin} dBm, {axes[0][3]} x {axes[1][3]} points", flush=True)
    try:
        _run_ade_parametric(path_ocean, cell_name, sweep_parameters=axes)
    finally:
        _close_ade_windows()
    print("Load-pull parametric sweep complete", flush=True)
    return path_output
