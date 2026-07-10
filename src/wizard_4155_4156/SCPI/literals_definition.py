from typing import Final, Literal, get_args

ModeType = Literal["SWEEP", "SAMP", "QSCV"]
BoolType = Literal["OFF", "ON"]
SMUModeType = Literal["COMM", "I", "V", "VPULSE", "IPULSE"]
VUModeType = Literal["V", "DVOL"]
FunctionType = Literal["CONS", "VAR1", "VAR2", "VARD"]

SMUnitType = Literal["SMU1", "SMU2", "SMU3", "SMU4"]
VMUnitType = Literal["VMU1", "VMU2"]
VSUnitType = Literal["VSU1", "VSU2"]

SourceUnitType = Literal[SMUnitType, VSUnitType]
MeasurementUnitType = Literal[SMUnitType, VMUnitType]
VoltageUnitType = Literal[VMUnitType, VSUnitType]
UnitType = Literal[SMUnitType, VMUnitType, VSUnitType]

IntegrationType = Literal["SHORT", "MED", "LONG"]
RangeType = Literal["AUTO", "FIX", "LIM"]

SamplingModeType = Literal["LINEAR", "L10", "L25", "L50", "THINNEDOUT"]
SConEventType = Literal["LOW", "HIGH", "ABSLOW", "ABSHIGH"]

SweepStopModeType = Literal["ABNORMAL", "COMPLIANCE", "OFF"]
PeriodSpecialType = Literal["INFINITY", "MINIMUM", "MAXIMUM"]
Var1ModeType = Literal["SINGLE", "DOUBLE"]
Var1SpacingType = Literal["LINEAR", "L10", "L25", "L50"]

QscvUnitType = Literal[SMUnitType, "DEFAULT"]

FormatDataType = Literal["ASC", "REAL"]
BorderType = Literal["NORM", "SWAP"]
AxisType = Literal["X", "Y1", "Y2"]

LITERAL_OPTIONS: Final[dict[str, tuple[str]]] = {
    "ModeType": get_args(ModeType),
    "BoolType": get_args(BoolType),
    "SMUModeType": get_args(SMUModeType),
    "VUModeType": get_args(VUModeType),
    "FunctionType": get_args(FunctionType),
    "SMUnitType": get_args(SMUnitType),
    "VMUnitType": get_args(VMUnitType),
    "VSUnitType": get_args(VSUnitType),
    "SourceUnitType": get_args(SourceUnitType),
    "MeasurementUnitType": get_args(MeasurementUnitType),
    "VoltageUnitType": get_args(VoltageUnitType),
    "UnitType": get_args(UnitType),
    "IntegrationType": get_args(IntegrationType),
    "RangeType": get_args(RangeType),
    "SamplingModeType": get_args(SamplingModeType),
    "SConEventType": get_args(SConEventType),
    "SweepStopModeType": get_args(SweepStopModeType),
    "PeriodSpecialType": get_args(PeriodSpecialType),
    "Var1ModeType": get_args(Var1ModeType),
    "Var1SpacingType": get_args(Var1SpacingType),
    "QscvUnitType": get_args(QscvUnitType),
    "FormatDataType": get_args(FormatDataType),
    "BorderType": get_args(BorderType),
    "AxisType": get_args(AxisType),
}
