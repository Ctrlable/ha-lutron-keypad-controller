from __future__ import annotations
_C='covers'
_B='default'
_A='_travel'
from homeassistant.components.number import NumberEntity,NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo,EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from.const import DOMAIN
def _controller_device():return DeviceInfo(identifiers={(DOMAIN,'controller')},name='Lutron Keypad Controller')
async def async_setup_entry(hass,entry,async_add_entities):
	B=entry;A=hass
	if not B.data.get('_controller'):return
	from.import _discover_cover_cycle_covers as D;C=[LutronGlobalTravelNumber(A,B)]
	for E in D(A):C.append(LutronShadeTravelNumber(A,B,E))
	async_add_entities(C)
class LutronGlobalTravelNumber(NumberEntity):
	_attr_has_entity_name=True;_attr_should_poll=False;_attr_entity_category=EntityCategory.CONFIG;_attr_name='Default shade travel time';_attr_native_unit_of_measurement='s';_attr_native_min_value=2;_attr_native_max_value=180;_attr_native_step=1;_attr_mode=NumberMode.BOX;_attr_icon='mdi:timer-cog-outline'
	def __init__(A,hass,entry):A._hass=hass;A._attr_unique_id=f"{entry.entry_id}_shade_travel_default"
	@property
	def device_info(self):return _controller_device()
	@property
	def native_value(self):A=self._hass.data.get(DOMAIN,{}).get(_A)or{};return float(A.get(_B)or 3e1)
	async def async_set_native_value(A,value):from.import _save_travel as B;C=A._hass.data.setdefault(DOMAIN,{}).setdefault(_A,{_B:3e1,_C:{}});C[_B]=float(value);await B(A._hass);A.async_write_ha_state()
class LutronShadeTravelNumber(NumberEntity):
	_attr_has_entity_name=True;_attr_should_poll=False;_attr_entity_category=EntityCategory.CONFIG;_attr_native_unit_of_measurement='s';_attr_native_min_value=0;_attr_native_max_value=180;_attr_native_step=1;_attr_mode=NumberMode.BOX;_attr_icon='mdi:timer-outline'
	def __init__(A,hass,entry,cover_id):B=cover_id;A._hass=hass;A._cover_id=B;D=B.split('.',1)[-1];A._attr_unique_id=f"{entry.entry_id}_shade_travel_{D}";C=hass.states.get(B);E=C.name if C and C.name else D.replace('_',' ').title();A._attr_name=f"{E} travel time"
	@property
	def device_info(self):return _controller_device()
	@property
	def native_value(self):A=self._hass.data.get(DOMAIN,{}).get(_A)or{};return float((A.get(_C)or{}).get(self._cover_id)or 0)
	async def async_set_native_value(A,value):
		B=value;from.import _save_travel as D;E=A._hass.data.setdefault(DOMAIN,{}).setdefault(_A,{_B:3e1,_C:{}});C=E.setdefault(_C,{})
		if B and float(B)>0:C[A._cover_id]=float(B)
		else:C.pop(A._cover_id,None)
		await D(A._hass);A.async_write_ha_state()