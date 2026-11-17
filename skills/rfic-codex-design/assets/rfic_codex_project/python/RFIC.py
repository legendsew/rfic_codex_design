import os
import subprocess
from pathlib import Path
import json

os.chdir(os.path.dirname(os.path.abspath(__file__)))

DEPLOY_FILE = Path(__file__).resolve().parent.parent / "json" / "deploy.json"
with DEPLOY_FILE.open("r",encoding="utf-8")as f:
    deploy = json.load(f)

home_dir = deploy["virtuoso_dir"]
tech = deploy["tech"]
mos_name = deploy["mos_name"]
model_path = deploy["model_path"]
setup_file_path = deploy["setup_file_path"]
emx_work_addr = deploy["emx_work_addr"]
proc_file_addr = deploy["proc_file_addr"]
emx_addr = deploy["emx_addr"]
lib_name = deploy["lib_name"]
project_name = deploy["project_name"]
simulation_path = deploy["simulation_path"]
model_type = deploy["model_type"]

run_path = f"{home_dir}/{project_name}/pcell/run.il"
dir_run = os.path.dirname(run_path)
os.makedirs(dir_run,exist_ok=True)

def create_lib():
    run_content = f'''
    load("{home_dir}/{project_name}/pcell/RFIC.il")
    create_lib("{lib_name}" "{home_dir}/{lib_name}" "{tech}")
    exit()
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    lib_result = subprocess.Popen(
        ["virtuoso","-nograph","-restore",f"{run_path}"],
        cwd=home_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        )
    lib_result.wait()
    return lib_result.returncode    

def register_symbolLib():
    run_content = f'''
    if(ddGetObj("rfic_codex_symbol")==nil then
        ddCreateLib("rfic_codex_symbol" "{home_dir}/{project_name}/rfic_codex_symbol")
        )
    exit()
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    register_result = subprocess.Popen(
        ["virtuoso","-nograph","-restore",f"{run_path}"],
        cwd=home_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        )
    register_result.wait()
    return register_result.returncode       

def generate_schematic(value,generation_code,transformer_name):
    run_content = f'''
    load("{home_dir}/{project_name}/pcell/RFIC.il")
    hiRegTimer("open_wizard()" 10)
    hiRegTimer("fill_wizard({value} \\"{tech}\\" \\"{mos_name}\\" \\"{lib_name}\\" \\"{generation_code}\\" \\"{transformer_name}\\" \\"{model_path}\\" \\"{setup_file_path}\\")" 20)
    hiRegTimer("close_log_window()" 30)
    hiRegTimer("exit()" 80)
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    generation_result = subprocess.Popen(
        ["virtuoso","-restore",f"{run_path}"],
        cwd=home_dir,
        )
    generation_result.wait()
    return generation_result.returncode

def start_emx(transformer_name,Freq_low,Freq_up):
    gds_generation = f'''
    strmout -library {lib_name} -topCell {transformer_name} -view layout -strmFile {emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.gds -runDir {emx_work_addr}/{lib_name}_{transformer_name}.work -logFile {emx_work_addr}/{lib_name}_{transformer_name}.work/strmOut.log -hierDepth 32 -case Preserve -convertDot node -pinAttNum 1
    '''
    emx_start = f'''
    {emx_addr} {emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.gds {transformer_name} {proc_file_addr} -e 1 -t 1 -v 0.5 --3d=* -p P000=pri_p -p P001=pri_m -p P002=sec_p -p P003=sec_m -i P000 -i P001 -i P002 -i P003 --sweep {Freq_low}e+09 {Freq_up}e+09 --sweep-stepsize 2e+08 --verbose=0 -l 2 --quasistatic --parallel=0 --simultaneous-frequencies=0 --recommended-memory --format=psf -s {emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.raw -y {emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.raw --format=matlab -y {emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.raw/{transformer_name}.y --format=touchstone -s {emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.s%dp
    '''

    gds_result = subprocess.run(
        gds_generation,
        shell=True,
        cwd=home_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    if gds_result.returncode !=0:
        print("Failed to generate .gds file.")
        return(1)
    emx_result = subprocess.run(
        emx_start,
        shell=True,
        cwd=home_dir,
    )
    if emx_result.returncode !=0:
        print("EMX simulation failed.")
        return(1)
    print("EMX simulation complete.")
    return(f"{emx_work_addr}/{lib_name}_{transformer_name}.work/{transformer_name}.s4p")

def copy_schematic(cell_name):
    run_content = f'''
    load("{home_dir}/{project_name}/pcell/RFIC.il")
    copy_schematic("{cell_name}" "{lib_name}")
    RFIC_Delete("{lib_name}" "{cell_name}" 3.2)
    cv = dbOpenCellViewByType("{lib_name}" "{cell_name}" "schematic" "" "a")
    place_PA_instance_and_wire(cv)
    edit_property(cv)
    generate_V(cv)
    exit()
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    edit_result = subprocess.Popen(
        ["virtuoso","-nograph","-restore",f"{run_path}"],
        cwd=home_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        )
    edit_result.wait()
    return edit_result.returncode

def generate_testbench(cell_name):
    run_content = f'''
    load("{home_dir}/{project_name}/pcell/RFIC.il")
    RFIC_Delete("{lib_name}" "{cell_name}" 3.2)
    cv = dbOpenCellViewByType("{lib_name}" "{cell_name}" "schematic" "" "a")
    place_in_transformer(cv 4 3)
    place_out_transformer(cv 4 1.5)
    exit()
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    testbench_result = subprocess.Popen(
        ["virtuoso","-nograph","-restore",f"{run_path}"],
        cwd=home_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        )
    testbench_result.wait()
    return testbench_result.returncode    

def start_ADL_simulation(cell_name,generation_code,R,L,Cp_in,Cs_in,Cp_out,Cs_out,s4p_path_in,s4p_path_out):
    parts = generation_code.split("/")
    freq = float(parts[1])
    vdd = float(parts[2])
    mul = int(parts[5])
    nof = int(parts[6])
    mul2 = int(parts[7])
    nof2 = int(parts[8])
    vbias = float(parts[9])

    path_ocean =f"{home_dir}/{project_name}/ocean/RFIC.ocn"
    dir_ocean = os.path.dirname(path_ocean) 
    path_output = f"{home_dir}/{project_name}/output/RFIC_{cell_name}/RFIC_{cell_name}.txt"
    dir_output = os.path.dirname(path_output)
    os.makedirs(dir_ocean,exist_ok=True)
    os.makedirs(dir_output,exist_ok=True)

    with open(path_output,"w") as report:
        report.write("Pin (dBm)\t\tPout (dBm)\tGain (dBm)\tIq (mA)\t\tIdd (mA)\t\tDE(%)\t\tS11\t\tS22\t\tKf_min\t\tB1f_min\n")

    ocn_content = f"""
simulator( 'spectre )
design(  "{lib_name}" "{cell_name}" "schematic")
resultsDir( "{simulation_path}/{cell_name}/spectre/schematic" )
modelFile(
        '("{model_path}" "{model_type}")
)
analysis('hb ?HBTranMode "Yes"  ?tstab "50p"  ?autoharms "yes"
                ?autotstab ""  ?autosteady "yes"  ?oversample list("1")  ?fundfreqs list("(Freq)")
                ?maxharms list("5")  )
analysis('dc ?saveOppoint t  ?param "temp"  )
analysis('sp ?ports list("/PORT0" "/PORT1")  ?start "1G"  ?stop "80G" 
                ?lin "2000")
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
            fprintf(fout "%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\n" Pin Pout Gain Iq*1000 Idd*1000 DE S11 S22 Kf B1f)
        )
        close(fout)
)
if(numberp(Pin) && numberp(Gain) && numberp(DE) then
    exit(0)
else
    exit(1)
)
"""
    with open(path_ocean,"w")as ocn:
            ocn.write(ocn_content)

    print("仿真中…")

    result = subprocess.run(
            f"ocean -restore {path_ocean} < /dev/null",
            cwd=home_dir,
            shell = True,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            )

    if result.returncode == 0:
            print("仿真完成")
    else:
            print(f"仿真失败({result.returncode})")

def Zin_ADL_simulation(cell_name,generation_code,R,L,ZLoad_real,ZLoad_imag):
    parts = generation_code.split("/")
    freq = float(parts[1])
    vdd = float(parts[2])
    mul = int(parts[5])
    nof = int(parts[6])
    mul2 = int(parts[7])
    nof2 = int(parts[8])
    vbias = float(parts[9])

    path_ocean =f"{home_dir}/{project_name}/ocean/RFIC.ocn"
    dir_ocean = os.path.dirname(path_ocean) 
    path_output = f"{home_dir}/{project_name}/output/RFIC_{cell_name}/RFIC_{cell_name}_Zin.txt"
    dir_output = os.path.dirname(path_output)
    os.makedirs(dir_ocean,exist_ok=True)
    os.makedirs(dir_output,exist_ok=True)

    with open(path_output,"w") as report:
        report.write("Zin_real\t\tZin_imag\t\n")

    ocn_content = f"""
simulator( 'spectre )
design(  "{lib_name}" "{cell_name}" "schematic")
resultsDir( "{simulation_path}/{cell_name}/spectre/schematic" )
modelFile(
        '("{model_path}" "{model_type}")
)
analysis('sp ?ports list("/PORT1" "/PORT2")  ?start "Freq*0.5"  ?stop "Freq*1.5"
                ?lin "2000"  )
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
    exit(0)
else
    exit(1)
)
"""
    with open(path_ocean,"w")as ocn:
            ocn.write(ocn_content)

    print("仿真中…")

    result = subprocess.run(
            f"ocean -restore {path_ocean} < /dev/null",
            cwd=home_dir,
            shell = True,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            )

    if result.returncode == 0:
            print("仿真完成")
    else:
            print(f"仿真失败({result.returncode})")

def measure_Zin(cell_name):
    run_content = f'''
    load("{home_dir}/{project_name}/pcell/RFIC.il")
    RFIC_Delete("{lib_name}" "{cell_name}" 3.2)
    cv = dbOpenCellViewByType("{lib_name}" "{cell_name}" "schematic" "" "a")
    measure_Zin(cv)
    port3(cv)
    exit()
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    measure_result = subprocess.Popen(
        ["virtuoso","-nograph","-restore",f"{run_path}"],
        cwd=home_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        )
    measure_result.wait()
    return measure_result.returncode

def load_pull(cell_name):
    path_output = f"{home_dir}/{project_name}/output/RFIC_{cell_name}/RFIC_{cell_name}_load_pull.txt"
    dir_output = os.path.dirname(path_output)
    os.makedirs(dir_output,exist_ok=True) 
    with open(path_output,"w") as report:
        report.write("ZLoad_real (Ohm)\t\tZLoad_imag(Ohm)\tPout (dBm)\tGain (dBm)\tIq (mA)\t\tIdd (mA)\t\tDE(%)\n")

    run_content = f'''
    load("{home_dir}/{project_name}/pcell/RFIC.il")
    RFIC_Delete("{lib_name}" "{cell_name}" 3.2)
    cv = dbOpenCellViewByType("{lib_name}" "{cell_name}" "schematic" "" "a")
    place_in_transformer(cv 4 3)
    port3(cv)
    exit()
    '''

    with open(run_path,"w")as run:
        run.write(run_content)

    load_pull_result = subprocess.Popen(
        ["virtuoso","-nograph","-restore",f"{run_path}"],
        cwd=home_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        )
    load_pull_result.wait()
    return load_pull_result.returncode     

def load_pull_simulation(cell_name,generation_code,R,L,pin,ZLoad_real,ZLoad_imag,Cp_in,Cs_in,s4p_path_in):
    path_output = f"{home_dir}/{project_name}/output/RFIC_{cell_name}/RFIC_{cell_name}_load_pull.txt"
    parts = generation_code.split("/")
    freq = float(parts[1])
    vdd = float(parts[2])
    mul = int(parts[5])
    nof = int(parts[6])
    mul2 = int(parts[7])
    nof2 = int(parts[8])
    vbias = float(parts[9])

    path_ocean =f"{home_dir}/{project_name}/ocean/RFIC.ocn"
    dir_ocean = os.path.dirname(path_ocean) 
    os.makedirs(dir_ocean,exist_ok=True)

    ocn_content = f"""
simulator( 'spectre )
design(  "{lib_name}" "{cell_name}" "schematic")
resultsDir( "{simulation_path}/{cell_name}/spectre/schematic" )
modelFile(
        '("{model_path}" "{model_type}")
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
run()
    fout = outfile("{path_output}" "a")
        if(openResults(resultsDir()) then
        Iout = harmonic(ih('hb "/PORT3/PLUS") 1)
        Vout = harmonic((vh('hb "/outp") - vh('hb "/outm")) 1)
        Pout = dbm((0.5 * ((real(Vout) * real(Iout)) + (imag(Vout) * imag(Iout)))))
        Idd = (- real(harmonic(i("/Vdd/PLUS" ?result "hb_fd") 0)))
        Pin = VAR("pin")
        ZLoad_real = VAR("ZLoad_real")
        ZLoad_imag =VAR("ZLoad_imag")
        Gain = (Pout - Pin)
        DE = (100 * (pow(10 ((Pout - 30) / 10)) / (VAR("Vdd") * Idd)))
        Iq = (- pv("Vdd" "i" ?result "dcOpInfo"))
        fprintf(fout "%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\t\\t%.2f\\n" ZLoad_real ZLoad_imag Pout Gain Iq*1000 Idd*1000 DE)
        )
        close(fout)
)
if(numberp(Pin) && numberp(Gain) && numberp(DE) then
    exit(0)
else
    exit(1)
)
"""
    with open(path_ocean,"w")as ocn:
            ocn.write(ocn_content)

    print("仿真中…")

    result = subprocess.run(
            f"ocean -restore {path_ocean} < /dev/null",
            cwd=home_dir,
            shell = True,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            )

    if result.returncode == 0:
            print("仿真完成")
    else:
            print(f"仿真失败({result.returncode})")