from __future__ import annotations
_F='new_state'
_E='entity_id'
_D='zwave_js'
_C=True
_B=False
_A=None
import asyncio,logging,time
from typing import Callable
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant,callback
from homeassistant.helpers.event import async_call_later,async_track_state_change_event
from.base import KeypadBackend
_LOGGER=logging.getLogger(__name__)
NUM_BUTTONS=5
BUTTON_BITMASKS=[1,2,4,8,16]
INDICATOR_ALL_OFF_VALUE=32
ZWAVE_INDICATOR_CC=135
ZWAVE_INDICATOR_PROPERTY='value'
REFRESH_SETTLE_S=.5
LED_COALESCE_WINDOW_S=.5
LED_SUPPRESS_WINDOW_S=2.
class _RFWC5LedManager:
	def __init__(A,hass,indicator_entity):A.hass=hass;A._indicator=indicator_entity;A._leds=[_B]*NUM_BUTTONS;A._debounce_unsub=_A;A._write_pending=_B;A._write_in_progress=_B;A._suppress_until=.0;A._write_lock=asyncio.Lock();A._needs_baseline=_C
	async def async_initialize(A):await A._refresh_and_read()
	def get(A,idx):return A._leds[idx]
	def suppress_external_writes(A,duration):A._suppress_until=time.monotonic()+duration
	@property
	def suppressed(self):return time.monotonic()<self._suppress_until
	async def async_set_button(A,idx,state):
		if not 0<=idx<NUM_BUTTONS:return
		if A._needs_baseline:
			B=A._read_raw()
			if B is not _A:A._leds=A._decode(B);A._needs_baseline=_B
		A._leds[idx]=state;A._schedule_write()
	@callback
	def ingest_indicator(self,raw):A=self;A._leds=A._decode(raw);A._needs_baseline=_B
	def _schedule_write(A):
		A._write_pending=_C
		if A._write_in_progress:return
		if A._debounce_unsub is not _A:A._debounce_unsub();A._debounce_unsub=_A
		@callback
		def B(_now):A._debounce_unsub=_A;A.hass.async_create_task(A._write_now())
		A._debounce_unsub=async_call_later(A.hass,LED_COALESCE_WINDOW_S,B)
	async def _refresh_and_read(A):
		async with A._write_lock:
			try:await A.hass.services.async_call(_D,'refresh_value',{_E:A._indicator},blocking=_C);await asyncio.sleep(REFRESH_SETTLE_S)
			except Exception as C:_LOGGER.debug('RFWC5 refresh_value unavailable at init: %s',C)
			B=A._read_raw()
			if B is not _A:A._leds=A._decode(B);A._needs_baseline=_B
	async def _write_now(A):
		if A._write_in_progress:return
		A._write_in_progress=_C;A._write_pending=_B
		try:
			async with A._write_lock:B=A._encode(A._leds);_LOGGER.debug('RFWC5 writing indicator: leds=%s value=%d',A._leds,B);await A.hass.services.async_call(_D,'set_value',{_E:A._indicator,'command_class':ZWAVE_INDICATOR_CC,'property':ZWAVE_INDICATOR_PROPERTY,'value':B},blocking=_C)
		except Exception as C:_LOGGER.error('RFWC5 indicator write failed: %s',C)
		finally:
			A._write_in_progress=_B
			if A._write_pending:A._schedule_write()
	def _read_raw(A):
		B=A.hass.states.get(A._indicator)
		if B is _A:return
		try:return int(float(B.state))
		except(ValueError,TypeError):return
	@staticmethod
	def _decode(raw):
		if raw==INDICATOR_ALL_OFF_VALUE:return[_B]*NUM_BUTTONS
		return[raw//A%2==1 for A in BUTTON_BITMASKS]
	@staticmethod
	def _encode(leds):A=sum(A for(A,B)in zip(BUTTON_BITMASKS,leds)if B);return A if A else INDICATOR_ALL_OFF_VALUE
class RFWC5Backend(KeypadBackend):
	source_domain=_D;license_product='rfwc5_controller';native_hold=_B;native_double_tap=_B
	def __init__(A):A._mgr=_A
	async def async_initialize(A,hass,controller):
		C=controller;D=C._config_entry;B=(D.data.get('indicator_entity')or'').strip()if D else''
		if B:
			A._mgr=_RFWC5LedManager(hass,B);await A._mgr.async_initialize()
			@callback
			def E(event):
				B=event.data.get(_F)
				if B is _A or A._mgr is _A:return
				try:A._mgr.ingest_indicator(int(float(B.state)))
				except(ValueError,TypeError):pass
			C._entity_tracking_unsubs.append(async_track_state_change_event(hass,[B],E))
	def subscribe(E,hass,controller):
		B='n';A=controller;F=A._config_entry;D=(F.data.get('basic_sensor')or'').strip()if F else'';C={B:_A}
		@callback
		def G(event):
			F=event.data.get(_F)
			if F is _A:return
			try:D=int(float(F.state))
			except(ValueError,TypeError):return
			if D==0:
				if C[B]is not _A:A.handle_button(C[B],'release');C[B]=_A
			elif D in(10,20,30,40,50):
				G=D//10;C[B]=G
				if E._mgr is not _A:E._mgr.suppress_external_writes(LED_SUPPRESS_WINDOW_S)
				A.handle_button(G,'press')
		if not D:_LOGGER.warning("RFWC5 '%s' has no basic_sensor configured — presses won't be seen",A.name);return lambda:_A
		H=async_track_state_change_event(hass,[D],G);_LOGGER.info("Lutron Keypad Controller '%s' registered (rfwc5, basic=%s)",A.name,D);return H
	async def async_write_led(A,hass,led_entity,is_on):
		if A._mgr is _A:return
		try:B=int(led_entity)-1
		except(ValueError,TypeError):return
		await A._mgr.async_set_button(B,is_on)
	async def async_find_leds(A,hass,config_entry):return{A:str(A)for A in range(1,NUM_BUTTONS+1)}