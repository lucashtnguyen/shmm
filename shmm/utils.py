from textwrap import dedent

import pandas as pd

def _formatter(df, filter_fnx, new_columns, fillna):
    """Formatter helper function. Filters and renames"""
    if filter_fnx:
        df = df.copy().loc[filter_fnx]

    return (
        df.loc[:, new_columns.keys()]
          .rename(columns=new_columns)
          .loc[:, new_columns.values()]
          .fillna(fillna)
    )

def format_subarea_table(df, fillna=-999, filter_fnx=None, n_imperv_col='N_Imperv',
                         n_perv_col='N_Perv', s_imperv_col='S_Imperv',
                         s_perv_col='S_Perv', pct_zero_col='PctZero',
                         route_to_col='RouteTo', pct_routed_col='PctRouted'):

    """Formatter helper function for the sub areas card."""
    new_columns = {
        n_imperv_col: 'N_Imperv',
        n_perv_col: 'N_Perv',
        s_imperv_col: 'S_Imperv',
        s_perv_col: 'S_Perv',
        pct_zero_col: 'PctZero',
        route_to_col: 'RouteTo',
        pct_routed_col: 'PctRouted'
    }

    return _formatter(df, filter_fnx, new_columns, fillna)

def format_outfall_table(df, fillna='', filter_fnx=None, elevation_col='Elevation',
                          type_col='Outfall_Type', stage_table_col='Stage_Table',
                          tide_gate_col='Tide_Gate', route_to_col='Route_To'):
    new_columns = {
        elevation_col: 'Invert_Elev',
        type_col: 'Outfall_Type',
        stage_table_col: 'Stage_Table_Time_Series',
        tide_gate_col: 'Tide_Gate',
        route_to_col: 'Route_To'
    }

    return _formatter(df, filter_fnx, new_columns, fillna)

def format_junction_table(df, fillna=-999, filter_fnx=None, elevation_col='Elevation',
                          max_depth_col='MaxDepth', init_depth_col='InitDepth',
                          surcharge_depth_col='SurDepth', aponded_col='Aponded'):
    new_columns = {
        elevation_col: 'Invert_Elev',
        max_depth_col: 'Max_Depth',
        init_depth_col: 'Init_Depth',
        surcharge_depth_col: 'Surcharge_Depth',
        aponded_col: 'Ponded_Area'
    }

    return _formatter(df, filter_fnx, new_columns, fillna)

def format_conduit_table(df, fillna=-999, filter_fnx=None, inlet_node_col='Inlet_Node',
                         outlet_node_col='Outlet_Node', length_col='Length',
                         manning_n_col='Manning_N', inlet_offset_col='Inlet_Offset',
                         outlet_offset_col='Outlet_Offset', init_flow_col='Init_Flow',
                         max_flow_col='Max_Flow'):

    new_columns = {
        inlet_node_col: 'Inlet_Node',
        outlet_node_col: 'Outlet_Node',
        length_col: 'Length',
        manning_n_col: 'Manning_N',
        inlet_offset_col: 'Inlet_Offset',
        outlet_offset_col: 'Outlet_Offset',
        init_flow_col: 'Init_Flow',
        max_flow_col: 'Max_Flow'
    }

    return _formatter(df, filter_fnx, new_columns, fillna)

def format_xsection_table(df, fillna=-999, filter_fnx=None, shape_col='Shape',
                         geom1_col='Geom1', geom2_col='Geom2', geom3_col='Geom3',
                         geom4_col='Geom4', barrels_col='Barrels'):

    new_columns = {
      shape_col: 'Shape',
      geom1_col: 'Geom1',
      geom2_col: 'Geom2',
      geom3_col: 'Geom3',
      geom4_col: 'Geom4',
      barrels_col: 'Barrels'
    }

    return _formatter(df, filter_fnx, new_columns, fillna)

def format_subcatchment_table(df, fillna=-999, filter_fnx=None, rain_gage_col='Rain_Gage',
                          outlet_col='Outlet', area_col='Area',pcnt_imperv_col='Pcnt_Imperv',
                          width_col='Width', pecnt_slope_col='Pecnt_Slope', curb_len_col='CurbLen',
                          snow_pack_col='SnowPack'):

    new_columns = {
        rain_gage_col: 'Rain_Gage',
        outlet_col: 'Outlet',
        area_col: 'Area',
        pcnt_imperv_col: 'Pcnt_Imperv',
        width_col: 'Width',
        pecnt_slope_col: 'Pecnt_Slope',
        curb_len_col: 'CurbLen',
        snow_pack_col: 'SnowPack',
    }

    return _formatter(df, filter_fnx, new_columns, fillna)

template = dedent("""\
    [TITLE]
    ;;Project Title/Notes

    [OPTIONS]
    ;;Option             Value
    FLOW_UNITS           CFS
    INFILTRATION         GREEN_AMPT
    FLOW_ROUTING         KINWAVE
    LINK_OFFSETS         DEPTH
    MIN_SLOPE            0
    ALLOW_PONDING        NO
    SKIP_STEADY_STATE    NO

    START_DATE           08/09/2018
    START_TIME           00:00:00
    REPORT_START_DATE    08/09/2018
    REPORT_START_TIME    00:00:00
    END_DATE             08/09/2018
    END_TIME             06:00:00
    SWEEP_START          01/01
    SWEEP_END            12/31
    DRY_DAYS             0
    REPORT_STEP          00:15:00
    WET_STEP             00:05:00
    DRY_STEP             01:00:00
    ROUTING_STEP         0:00:30

    INERTIAL_DAMPING     PARTIAL
    NORMAL_FLOW_LIMITED  BOTH
    FORCE_MAIN_EQUATION  H-W
    VARIABLE_STEP        0.75
    LENGTHENING_STEP     0
    MIN_SURFAREA         12.557
    MAX_TRIALS           8
    HEAD_TOLERANCE       0.005
    SYS_FLOW_TOL         5
    LAT_FLOW_TOL         5
    MINIMUM_STEP         0.5
    THREADS              1

    [EVAPORATION]
    ;;Data Source    Parameters
    ;;-------------- ----------------
    CONSTANT         0.0
    DRY_ONLY         NO

    [RAINGAGES]
    ;;Name           Format    Interval SCF      Source
    ;;-------------- --------- ------ ------ ----------
    !1                INTENSITY 1:00     1.0      TIMESERIES *

    [SUBCATCHMENTS]
    ;;Name           Rain Gage        Outlet           Area     %Imperv  Width    %Slope   CurbLen  SnowPack
    ;;-------------- ---------------- ---------------- -------- -------- -------- -------- -------- ----------------
    !Subcatchment_1  *                !Node_1          5        25       500      0.5      0

    [SUBAREAS]
    ;;Subcatchment   N-Imperv   N-Perv     S-Imperv   S-Perv     PctZero    RouteTo    PctRouted
    ;;-------------- ---------- ---------- ---------- ---------- ---------- ---------- ----------
    !Subcatchment_1  0.01       0.1        0.05       0.05       25         OUTLET

    [INFILTRATION]
    ;;Subcatchment   Suction    Ksat       IMD
    ;;-------------- ---------- ---------- ----------
    !Subcatchment_1  3.0        0.5        4

    [JUNCTIONS]
    ;;Name           Elevation  MaxDepth   InitDepth  SurDepth   Aponded
    ;;-------------- ---------- ---------- ---------- ---------- ----------
    !Node_1          0          0          0          0          0

    [OUTFALLS]
    ;;Name           Elevation  Type       Stage Data       Gated    Route To
    ;;-------------- ---------- ---------- ---------------- -------- ----------------
    !Node_3          0          FREE                        NO

    [STORAGE]
    ;;Name           Elev.    MaxDepth   InitDepth  Shape      Curve Name/Params            N/A      Fevap    Psi      Ksat     IMD
    ;;-------------- -------- ---------- ----------- ---------- ---------------------------- -------- --------          -------- --------
    !Node_2          0        0          0          FUNCTIONAL 1000      0         0        0        0

    [CONDUITS]
    ;;Name           From Node        To Node          Length     Roughness  InOffset   OutOffset  InitFlow   MaxFlow
    ;;-------------- ---------------- ---------------- ---------- ---------- ---------- ---------- ---------- ----------
    !Conduit_1       !Node_1          !Node_2          400        0.01       0          0          0          0
    !Conduit_2       !Node_2          !Node_3          400        0.01       0          0          0          0

    [WEIRS]
    ;;Name           From Node        To Node          Type         CrestHt    Qcoeff     Gated    EndCon   EndCoeff   Surcharge  RoadWidth  RoadSurf
    ;;-------------- ---------------- ---------------- ------------ ---------- ---------- -------- -------- ---------- ---------- ---------- ----------
    !Weir            !Node_2          !Node_3          TRANSVERSE   0          3.33       NO       0        0          YES

    [XSECTIONS]
    ;;Link           Shape        Geom1            Geom2      Geom3      Geom4      Barrels    Culvert
    ;;-------------- ------------ ---------------- ---------- ---------- ---------- ---------- ----------
    !Conduit_1       CIRCULAR     1                0          0          0          1
    !Conduit_2       CIRCULAR     1                0          0          0          1
    !Weir            RECT_OPEN    1                1          0          0

    [TIMESERIES]
    ;;Name           Date       Time       Value
    ;;-------------- ---------- ---------- ----------
    !ts            FILE "C:\.."

    [REPORT]
    ;;Reporting Options
    INPUT      NO
    CONTROLS   NO
    SUBCATCHMENTS ALL
    NODES ALL
    LINKS ALL

    [TAGS]

    [MAP]
    DIMENSIONS 0.000 0.000 10000.000 10000.000
    Units      None

    [COORDINATES]
    ;;Node           X-Coord            Y-Coord
    ;;-------------- ------------------ ------------------
    !Node_1          1839.677           6493.656
    !Node_3          5080.738           6320.646
    !Node_2          3673.587           6505.190

    [VERTICES]
    ;;Link           X-Coord            Y-Coord
    ;;-------------- ------------------ ------------------
    !Conduit_1       2739.331           7254.902
    !Conduit_1       3431.373           7266.436
    !Weir            4504.037           6989.619

    [Polygons]
    ;;Subcatchment   X-Coord            Y-Coord
    ;;-------------- ------------------ ------------------
    !Subcatchment_1  -1113.033          5628.604
    !Subcatchment_1  524.798            5605.536
    !Subcatchment_1  513.264            7289.504
    !Subcatchment_1  -1101.499          7301.038

    [SYMBOLS]
    ;;Gage           X-Coord            Y-Coord
    ;;-------------- ------------------ ------------------
    !1               1                  2
"""
)