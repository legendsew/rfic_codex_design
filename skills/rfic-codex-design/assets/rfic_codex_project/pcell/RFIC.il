procedure(create_lib(lib_name lib_path Tech)
    if(ddGetObj(lib_name)==nil then
        ddCreateLib(lib_name lib_path)
        techBindTechFile(ddGetObj(lib_name) Tech)
        )
    )

procedure(open_wizard()
    _Passive_tool_APP_FieldFormCB()
    )

procedure(fill_wizard(value Tech mos_name lib_name Generation_Code cell_name model_path setup_file_path)
    if(value == 4 then
        hiGetCurrentForm()->Passive_tool_APP_Field->value = 4
        Active_Field_CallBack_Load()
        hiGetCurrentForm()->Passive_tool_APP_Field->page4->t_sourceLibComb->value="CSPA"
        hiGetCurrentForm()->Passive_tool_APP_Field->page4->t_sourceCellComb->value="CSPA_lvt4t"
        hiGetCurrentForm()->Passive_tool_APP_Field->page4->t_destnmos4tLibComb->value=Tech
        hiGetCurrentForm()->Passive_tool_APP_Field->page4->t_destnmos4tCellComb->value=mos_name
        hiGetCurrentForm()->Passive_tool_APP_Field->page4->model_pathField->value=model_path
        hiGetCurrentForm()->Passive_tool_APP_Field->page4->VariablesSetupField->value= Generation_Code
        ApplyPress(RFIC_PDKToolForm)
        )
    if(value == 3 then
        hiGetCurrentForm()->Passive_tool_APP_Field->value = 3
        hiGetCurrentForm()->Passive_tool_APP_Field->page3->WEB_CODE_setup_pathField->value = setup_file_path
        _setupLoadField()
        hiGetCurrentForm()->Passive_tool_APP_Field->page3->WEB_CODE_Excelweb_outputField->value= Generation_Code
        hiGetCurrentForm()->Passive_tool_APP_Field->page3->WEB_CODE_ExcelLibField->value=lib_name
        hiGetCurrentForm()->Passive_tool_APP_Field->page3->WEB_CODE_ExcelCell_nameField->value= cell_name
        _WEB_CODE_ExcelApplyFieldCB()
        )
    )

procedure(close_log_window()
    system("xdotool search --name \"Stream in translation complete\" key --window %@ Escape")
    )

procedure(BBoxRightOfX(bBox xLimit)
    let((ll lx)
        ll = car(bBox)
        lx = car(ll)
        lx >= xLimit
        )
    )

procedure(RFIC_Delete(libName cellName xLimit)
    let((cv deleteInstList deleteShapeList deleteNetList)

        cv = dbOpenCellViewByType(libName cellName "schematic" "" "a")

        deleteInstList = nil
        deleteShapeList = nil
        deleteNetList = nil

        ;1.删除所有无源instance
        foreach(inst cv~>instances
            when(
                inst~>bBox &&
                car(car(inst~>bBox)) >= xLimit

                deleteInstList = cons(inst deleteInstList)
            )
        )

        foreach(inst deleteInstList
            errset(
                dbDeleteObject(inst)
                t
            )
        )

        ; 2. 删除 x >= xLimit 的 shape / wire / label / ellipse
        foreach(fig cv~>shapes
            when(fig~>bBox && BBoxRightOfX(fig~>bBox xLimit)
                deleteShapeList = cons(fig deleteShapeList)
            )
        )
        foreach(fig deleteShapeList
            errset(dbDeleteObject(fig) t)
        )
        schCheck(cv)
        ; 3. 删除已经空掉的 net
        foreach(net cv~>nets
            when(length(net~>instTerms) == 0 &&
                length(net~>terms) == 0 &&
                length(net~>figs) == 0
                deleteNetList = cons(net deleteNetList)
            )
        )

        foreach(net deleteNetList
            errset(dbDeleteObject(net) t)
        )

        schCheck(cv)
        dbSave(cv)
        dbClose(cv)
        )
    )

procedure(copy_schematic(cell_name lib_name)
    let((cv sourceCellViewID)
        sourceCellViewID = dbOpenCellViewByType("CSPA" "CSPA_lvt4t" "schematic" "" "r")
        cv = dbCopyCellView(
            sourceCellViewID
            lib_name
            cell_name
            "schematic"
            nil
            nil
            t
            )
        dbClose(sourceCellViewID)
        dbSave(cv)
        dbClose(cv)
        )
    )

procedure(Createwire(cv wirelist)
    schCreateWire(
        cv
        "draw"
        "full"
        wirelist
        0.0625
        0.0625
        0.0
        )
    )

procedure(place_PA_instance_and_wire(cv)
    let((ind_master res_master)
        ind_master = dbOpenCellViewByType("analogLib" "ind" "symbol" "" "r")
        res_master = dbOpenCellViewByType("analogLib" "res" "symbol" "" "r")
        schCreateInst(
            cv
            ind_master
            "L1"
            -0.875:3.5
            "R90"
            )
        schCreateInst(
            cv
            ind_master
            "L2"
            2.375:3.5
            "R90"
            )
        schCreateInst(
            cv
            res_master
            "R1"
            -0.4375:0
            "R90"
            )
        schCreateInst(
            cv
            res_master
            "R2"
            2.1875:0
            "R90"
            )
        Createwire(cv list(-0.5:3.5 2.375:3.5))
        Createwire(cv list(-0.0625:0 2.1875:0))
        schCreateWireLabel(
            cv
            nil
            1:3.5
            "vdda_"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            1:0
            "bias"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCheck(cv)
        dbSave(cv)
        ;dbClose(cv)
        )
    )

procedure(edit_property(cv)
    let((R1 R2 L1 L2 M1 M2 M3 M4)
        R1 = car(setof(inst cv~>instances inst~>name == "R1"))
        R2 = car(setof(inst cv~>instances inst~>name == "R2"))
        L1 = car(setof(inst cv~>instances inst~>name == "L1"))
        L2 = car(setof(inst cv~>instances inst~>name == "L2"))
        M1 = car(setof(inst cv~>instances inst~>name == "M1"))
        M2 = car(setof(inst cv~>instances inst~>name == "M2"))
        M3 = car(setof(inst cv~>instances inst~>name == "M3"))
        M4 = car(setof(inst cv~>instances inst~>name == "M4"))
        dbReplaceProp(R1 "r" "string" "R")
        dbReplaceProp(R2 "r" "string" "R")
        dbReplaceProp(L1 "l" "string" "L")
        dbReplaceProp(L2 "l" "string" "L")
        foreach(inst list(M1 M3)
            dbReplaceProp(inst "w" "string" "1u")
            dbReplaceProp(inst "fingers" "string" "NoF")
            dbReplaceProp(inst "simM" "string" "Mul")
            dbReplaceProp(inst "totalM" "string" "NoF*Mul")
            dbReplaceProp(inst "wf" "string" "1e-06*NoF")
            dbReplaceProp(inst "nrd" "string" "(NoF-int(NoF/2)*2)*(1e-07*1e-07/(1e-07+1e-07*(NoF-1))/1e-06)+(NoF+1-int((NoF+1)/2)*2)*(1e-07/NoF/1e-06)")
            dbReplaceProp(inst "nrs" "string" "(NoF-int(NoF/2)*2)*(1e-07*1e-07/(1e-07+1e-07*(NoF-1))/1e-06)+(NoF+1-int((NoF+1)/2)*2)*(1e-07*1e-07*1e-07/(1e-07*1e-07*(NoF-2)+1e-07*(1e-07+1e-07))/1e-06)")
            dbReplaceProp(inst "pd" "string" "(NoF-int(NoF/2)*2)*((1.75e-07+((NoF-1)*2e-07)/2+0)*2+(NoF+1)*1e-06)+(NoF+1-int((NoF+1)/2)*2)*(((NoF/2)*2e-07)*2+NoF*1e-06)")
            dbReplaceProp(inst "ps" "string" "(NoF-int(NoF/2)*2)*((1.75e-07+((NoF-1)*2e-07)/2+0)*2+(NoF+1)*1e-06)+(NoF+1-int((NoF+1)/2)*2)*((1.75e-07+1.75e-07+(NoF/2-1)*2e-07+0+0)*2+(NoF+2)*1e-06)")
            dbReplaceProp(inst "ad" "string" "((NoF-int(NoF/2)*2)*(1.75e-07+((NoF-1)*2e-07)/2+0)+(NoF+1-int((NoF+1)/2)*2)*((NoF/2)*2e-07))*1e-06")
            dbReplaceProp(inst "as" "string" "((NoF-int(NoF/2)*2)*(1.75e-07+((NoF-1)*2e-07)/2+0)+(NoF+1-int((NoF+1)/2)*2)*(1.75e-07+1.75e-07+(NoF/2-1)*2e-07+0+0))*1e-06")
            )
        foreach(inst list(M2 M4)
            dbReplaceProp(inst "w" "string" "1u")
            dbReplaceProp(inst "fingers" "string" "NoF2")
            dbReplaceProp(inst "simM" "string" "Mul2")
            dbReplaceProp(inst "totalM" "string" "NoF2*Mul2")
            dbReplaceProp(inst "wf" "string" "1e-06*NoF2")
            dbReplaceProp(inst "nrd" "string" "(NoF2-int(NoF2/2)*2)*(1e-07*1e-07/(1e-07+1e-07*(NoF2-1))/1e-06)+(NoF2+1-int((NoF2+1)/2)*2)*(1e-07/NoF2/1e-06)")
            dbReplaceProp(inst "nrs" "string" "(NoF2-int(NoF2/2)*2)*(1e-07*1e-07/(1e-07+1e-07*(NoF2-1))/1e-06)+(NoF2+1-int((NoF2+1)/2)*2)*(1e-07*1e-07*1e-07/(1e-07*1e-07*(NoF2-2)+1e-07*(1e-07+1e-07))/1e-06)")
            dbReplaceProp(inst "pd" "string" "(NoF2-int(NoF2/2)*2)*((1.75e-07+((NoF2-1)*2e-07)/2+0)*2+(NoF2+1)*1e-06)+(NoF2+1-int((NoF2+1)/2)*2)*(((NoF2/2)*2e-07)*2+NoF2*1e-06)")
            dbReplaceProp(inst "ps" "string" "(NoF2-int(NoF2/2)*2)*((1.75e-07+((NoF2-1)*2e-07)/2+0)*2+(NoF2+1)*1e-06)+(NoF2+1-int((NoF2+1)/2)*2)*((1.75e-07+1.75e-07+(NoF2/2-1)*2e-07+0+0)*2+(NoF2+2)*1e-06)")
            dbReplaceProp(inst "ad" "string" "((NoF2-int(NoF2/2)*2)*(1.75e-07+((NoF2-1)*2e-07)/2+0)+(NoF2+1-int((NoF2+1)/2)*2)*((NoF2/2)*2e-07))*1e-06")
            dbReplaceProp(inst "as" "string" "((NoF2-int(NoF2/2)*2)*(1.75e-07+((NoF2-1)*2e-07)/2+0)+(NoF2+1-int((NoF2+1)/2)*2)*(1.75e-07+1.75e-07+(NoF2/2-1)*2e-07+0+0))*1e-06")
            )
        schCheck(cv)
        dbSave(cv)
        ; dbClose(cv) ; Keep cv open for network placement and testbench creation.
        )
    )

procedure(place_in_transformer(cv x y)
    let((nport_master nport port_master port)
        nport_master = dbOpenCellViewByType("rfic_codex_symbol" "inport_symbol" "symbol" "" "r")
        port_master = dbOpenCellViewByType("analogLib" "port" "symbol" "" "r")
        schCreateInst(
            cv
            nport_master
            "in_net"
            x:y
            "R0"
            )
        schCreateInst(
            cv
            port_master
            "PORT0"
            (x+2):y
            "R0"
            )
        nport = car(setof(inst cv~>instances inst~>name == "in_net"))
        dbReplaceProp(nport "Cp" "string" "Cp_in")
        dbReplaceProp(nport "Cs" "string" "Cs_in")
        dbReplaceProp(nport "s4p_path" "string" "s4p_path_in")
        Createwire(cv list((x-0.125):(y-0.1875) (x+0.0625):(y-0.1875)))
        Createwire(cv list((x+0.9375):y (x+1.125):y))
        Createwire(cv list((x+0.9375):(y-0.375) (x+1.125):(y-0.375)))
        Createwire(cv list((x+2):y (x+2):(y+0.25)))
        Createwire(cv list((x+2):(y-0.5) (x+2):(y-0.75)))
        schCreateWireLabel(
            cv
            nil
            (x-0.125):(y-0.1875)
            "IN"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+1.125):y
            "inp"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+1.125):(y-0.375)
            "inm"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+2):(y+0.25)
            "IN"
            "centerCenter"
            "R90"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+2):(y-0.75)
            "vssa"
            "centerCenter"
            "R90"
            "stick"
            0.0625
            nil
            ) 
        port = car(setof(inst cv~>instances inst~>name == "PORT0"))
        dbReplaceProp(port "freq" "string" "Freq")
        dbReplaceProp(port "vaDBm" "string" "pin")
        schCheck(cv)
        dbSave(cv)
        ; dbClose由Virtuoso退出时统一处理
        )
    )

procedure(place_out_transformer(cv x y)
    let((nport_master nport port_master)
        nport_master = dbOpenCellViewByType("rfic_codex_symbol" "outport_symbol" "symbol" "" "r")
        port_master = dbOpenCellViewByType("analogLib" "port" "symbol" "" "r")
        schCreateInst(
            cv
            nport_master
            "out_net"
            x:y
            "R0"
            )
        schCreateInst(
            cv
            port_master
            "PORT1"
            (x+2):y
            "R0"
            )
        nport = car(setof(inst cv~>instances inst~>name == "out_net"))
        dbReplaceProp(nport "Cp" "string" "Cp_out")
        dbReplaceProp(nport "Cs" "string" "Cs_out")
        dbReplaceProp(nport "s4p_path" "string" "s4p_path_out")
        Createwire(cv list((x-0.125):(y+0.25) (x+0.0625):(y+0.25)))
        Createwire(cv list((x-0.125):(y-0.125) (x+0.0625):(y-0.125)))
        Createwire(cv list((x+0.9375):(y+0.0625) (x+1.125):(y+0.0625)))
        Createwire(cv list((x+2):y (x+2):(y+0.25)))
        Createwire(cv list((x+2):(y-0.5) (x+2):(y-0.75)))
        schCreateWireLabel(
            cv
            nil
            (x-0.125):(y+0.25)
            "outp"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x-0.125):(y-0.125)
            "outm"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+1.125):(y+0.0625)
            "OUT"
            "centerCenter"
            "R0"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+2):(y+0.25)
            "OUT"
            "centerCenter"
            "R90"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            (x+2):(y-0.75)
            "vssa"
            "centerCenter"
            "R90"
            "stick"
            0.0625
            nil
            )    
        schCheck(cv)
        dbSave(cv)
        ; dbClose由Virtuoso退出时统一处理
        )
    )

procedure(generate_V(cv)
    let((vdc_master gnd_master x vdc)
        port_master = dbOpenCellViewByType("analogLib" "port" "symbol" "" "r")
        vdc_master = dbOpenCellViewByType("analogLib" "vdc" "symbol" "" "r")
        gnd_master = dbOpenCellViewByType("analogLib" "gnd" "symbol" "" "r")
        x = -0.5
        foreach(V list("Vbias" "Vdd" "0")
            schCreateInst(
                cv
                vdc_master
                V
                x:5
                "R0"
                )
            vdc = car(setof(inst cv~>instances inst~>name == V))
            dbReplaceProp(vdc "vdc" "string" V)
            Createwire(cv list(x:5 x:5.25))
            case(V
                ("Vbias"
                    schCreateWireLabel(
                        cv
                        nil
                        x:5.25
                        "bias"
                        "centerCenter"
                        "R90"
                        "stick"
                        0.0625
                        nil
                        )
                    )
                ("Vdd"
                    schCreateWireLabel(
                        cv
                        nil
                        x:5.25
                        "vdda_"
                        "centerCenter"
                        "R90"
                        "stick"
                        0.0625
                        nil
                        )
                    )
                ("0"
                    schCreateWireLabel(
                        cv
                        nil
                        x:5.25
                        "vssa"
                        "centerCenter"
                        "R90"
                        "stick"
                        0.0625
                        nil
                        )
                    )
                )
            x = x+0.5
            )
        Createwire(cv list(-0.5:4.625 0.5:4.625))
        schCreateInst(
            cv
            gnd_master
            ""
            0.5:4.625
            "R0"
            )
        schCheck(cv)
        dbSave(cv)
        dbClose(cv)
        )
    )



procedure(measure_Zin(cv)
    let((port_master x)
        port_master = dbOpenCellViewByType("analogLib" "port" "symbol" "" "r")
        x = 4
        foreach(port_name list("PORT1" "PORT2")    
            schCreateInst(
                cv
                port_master
                port_name
                x:4
                "R0"
                )
            Createwire(cv list(x:4 x:4.25))
            Createwire(cv list(x:3.25 x:3.5))
            schCreateWireLabel(
                cv
                nil
                x:3.25
                "vssa"
                "centerCenter"
                "R90"
                "stick"
                0.0625
                nil
                )
            if(port_name == "PORT1" then
                schCreateWireLabel(
                    cv
                    nil
                    x:4.25
                    "inp"
                    "centerCenter"
                    "R90"
                    "stick"
                    0.0625
                    nil
                    )
                )
            if(port_name == "PORT2" then
                schCreateWireLabel(
                    cv
                    nil
                    x:4.25
                    "inm"
                    "centerCenter"
                    "R90"
                    "stick"
                    0.0625
                    nil
                    )
                )
            x = x+0.5
            )
        schCheck(cv)
        dbSave(cv)
        ;dbClose(cv)
        )                
    )

procedure(port3(cv)
    let((port_master port3)
        port_master = dbOpenCellViewByType("analogLib" "port" "symbol" "" "r")    
        schCreateInst(
            cv
            port_master
            "PORT3"
            4:1.5
            "R0"
            )
        Createwire(cv list(4:1.5 4:1.75))
        Createwire(cv list(4:0.75 4:1))
        schCreateWireLabel(
            cv
            nil
            4:1.75
            "outp"
            "centerCenter"
            "R90"
            "stick"
            0.0625
            nil
            )
        schCreateWireLabel(
            cv
            nil
            4:0.75
            "outm"
            "centerCenter"
            "R90"
            "stick"
            0.0625
            nil
            )
        port3 = car(setof(inst cv~>instances inst~>name == "PORT3"))
        dbReplaceProp(port3 "r" "string" "ZLoad_real")
        dbReplaceProp(port3 "x" "string" "ZLoad_imag")    
        schCheck(cv)
        dbSave(cv)
        dbClose(cv)        
        )
    )