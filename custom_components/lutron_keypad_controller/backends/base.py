from __future__ import annotations
from abc import ABC,abstractmethod
from typing import Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
class KeypadBackend(ABC):
	source_domain:str='';license_product:str='lutron_keypad_controller';native_hold:bool=False;native_double_tap:bool=False
	async def async_initialize(A,hass,controller):0
	@abstractmethod
	def subscribe(self,hass,controller):0
	@abstractmethod
	async def async_write_led(self,hass,led_entity,is_on):0
	@abstractmethod
	async def async_find_leds(self,hass,config_entry):0