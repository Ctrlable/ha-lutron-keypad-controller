from __future__ import annotations
_A='caseta'
from homeassistant.config_entries import ConfigEntry
from.base import KeypadBackend
from.caseta import CasetaBackend
from.lip import LipBackend
from.rfwc5 import RFWC5Backend
_BACKENDS={_A:CasetaBackend,'lip':LipBackend,'rfwc5':RFWC5Backend}
def get_backend(config_entry):
	A=config_entry;B=_A
	if A is not None:B=A.data.get('backend')or _A
	return _BACKENDS.get(B,CasetaBackend)()
__all__=['KeypadBackend','CasetaBackend','LipBackend','RFWC5Backend','get_backend']