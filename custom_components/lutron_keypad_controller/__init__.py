from __future__ import annotations
_AN='entity_id'
_AM='controller'
_AL='current_position'
_AK='stop_cover'
_AJ='lutron_type'
_AI='color_temp_kelvin'
_AH='debug_leds'
_AG='open_cover'
_AF='_sidebar_show'
_AE='/lutron_keypad_panel.js'
_AD='area_name'
_AC='leap_button_number'
_AB='lower_button'
_AA='raise_button'
_A9='configurable_buttons'
_A8='button_number'
_A7='off_level'
_A6='generic'
_A5='scene_id'
_A4='transition'
_A3='unavailable'
_A2='controllers'
_A1='number'
_A0='close_cover'
_z='cover'
_y='_travel'
_x='jti'
_w='product'
_v='source'
_u='entry_controllers'
_t='keypad_type'
_s='leap_button_map'
_r='button_names'
_q='hs_color'
_p='up'
_o='closed'
_n='off'
_m='license_keys'
_l='not_found'
_k='none'
_j='button'
_i='button_numbers'
_h='_v2_blocks'
_g='hold'
_f='double_tap'
_e='brightness_pct'
_d='down'
_c='color_temp'
_b='default'
_a='license_key'
_Z='success'
_Y='.'
_X='covers'
_W='unknown'
_V='data'
_U='buttons'
_T='model'
_S='model_number'
_R='lutron_caseta'
_Q='cycle_dim'
_P='switch'
_O='_controller'
_N='light.'
_M='scene_group'
_L='entry_id'
_K='serial'
_J='entities'
_I='light'
_H='brightness'
_G='name'
_F='device_id'
_E='id'
_D='type'
_C=False
_B=True
_A=None
import asyncio,logging,time
from pathlib import Path
from typing import Any
import voluptuous as vol,homeassistant.helpers.config_validation as cv
from homeassistant.components import frontend,websocket_api
from homeassistant.core import HomeAssistant,Event,CoreState,callback
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers import entity_platform,entity_registry as er,device_registry as dr
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
from homeassistant.loader import async_get_integration
from.license import LicenseError,check_revocation_online,load_license_cache,periodic_revocation_check,recall_license_key,remember_license_key,save_license_cache,validate_license_offline
from homeassistant.const import SERVICE_TURN_ON,SERVICE_TURN_OFF,SERVICE_TOGGLE,ATTR_ENTITY_ID
_COMPONENT_DIR=Path(__file__).parent
from.const import DOMAIN,LUTRON_EVENT,CONF_BUTTONS,CONF_BUTTON_NUMBER,CONF_BUTTON_LABEL,CONF_ACTION_TYPE,CONF_ACTION_TARGET,CONF_ACTION_PARAMS,CONF_LED_ENTITY,CONF_LED_INVERT,CONF_LED_MODE,CONF_TARGET_BRIGHTNESS,CONF_TARGET_COLOR_TEMP,CONF_ENTITY_SETTINGS,LED_MODE_ROOM,LED_MODE_PATHWAY,LED_MODE_SCENE,CONF_DEVICE_SERIAL,CONF_DEVICE_NAME,CONF_AREA_NAME,CONF_KEYPAD_TYPE,ACTION_STATEFUL_SCENE,ACTION_HA_SCENE,ACTION_AUTOMATION,ACTION_SCRIPT,ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION,ACTION_COVER_CYCLE,ACTION_LIGHT_CYCLE_DIM,ACTION_RAISE,ACTION_LOWER,ACTION_NONE,DIM_CYCLE_LEVELS,COVER_STATE_OPEN,COVER_STATE_STOP,COVER_STATE_CLOSE,RAISE_LOWER_STEP,ATTR_ACTIVE_SCENE,ATTR_LAST_ACTION,ATTR_COVER_STATES,ATTR_LIGHT_DIM_STEPS,get_button_layout,get_button_list,KEYPAD_GENERIC
_LOGGER=logging.getLogger(__name__)
BUTTON_SCHEMA=vol.Schema({vol.Required(CONF_BUTTON_NUMBER):cv.positive_int,vol.Optional(CONF_BUTTON_LABEL,default=''):cv.string,vol.Required(CONF_ACTION_TYPE):vol.In([ACTION_STATEFUL_SCENE,ACTION_HA_SCENE,ACTION_AUTOMATION,ACTION_SCRIPT,ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION,ACTION_COVER_CYCLE,ACTION_LIGHT_CYCLE_DIM,ACTION_RAISE,ACTION_LOWER,ACTION_NONE]),vol.Optional(CONF_ACTION_TARGET):vol.Any(cv.entity_id,[cv.entity_id],cv.string),vol.Optional(CONF_ACTION_PARAMS,default={}):dict,vol.Optional(CONF_LED_ENTITY):cv.entity_id})
KEYPAD_SCHEMA=vol.Schema({vol.Required(_G):cv.string,vol.Optional(CONF_DEVICE_SERIAL,default=''):cv.string,vol.Optional(CONF_DEVICE_NAME,default=''):cv.string,vol.Optional(CONF_AREA_NAME,default=''):cv.string,vol.Optional(CONF_KEYPAD_TYPE,default=_A6):cv.string,vol.Optional(_M,default=''):cv.string,vol.Required(CONF_BUTTONS):vol.All(cv.ensure_list,[BUTTON_SCHEMA])})
CONFIG_SCHEMA=vol.Schema({DOMAIN:vol.Schema({vol.Required('keypads'):vol.All(cv.ensure_list,[KEYPAD_SCHEMA])})},extra=vol.ALLOW_EXTRA)
PLATFORMS=['sensor',_P,'select','text']
def _normalize_action_target(target_raw,action_type):
	A=target_raw
	if not A:return A
	if isinstance(A,list):B=[A.strip()for A in A if str(A).strip()]
	elif isinstance(A,str)and','in A:B=[A.strip()for A in A.split(',')if A.strip()]
	else:B=[A]if A else[]
	if not B:return A
	if action_type in(ACTION_STATEFUL_SCENE,ACTION_HA_SCENE,ACTION_AUTOMATION,ACTION_SCRIPT):return B[0]
	return B
def _build_buttons_from_options(buttons_options):
	K='press_on';F=[]
	for(L,A)in buttons_options.items():
		try:M=int(L)
		except ValueError:continue
		if not A.get('enabled',_B):continue
		D=A.get(K);C={**A,**D}if D is not _A else A;E=C.get(CONF_ACTION_TYPE,ACTION_NONE)
		if not E or E==ACTION_NONE:continue
		B={CONF_BUTTON_NUMBER:M,CONF_BUTTON_LABEL:A.get(CONF_BUTTON_LABEL,''),CONF_ACTION_TYPE:E};G=_normalize_action_target(C.get(CONF_ACTION_TARGET,''),E)
		if G:B[CONF_ACTION_TARGET]=G
		if A.get(CONF_LED_ENTITY):B[CONF_LED_ENTITY]=A[CONF_LED_ENTITY]
		if A.get(CONF_LED_INVERT):B[CONF_LED_INVERT]=_B
		if C.get(_M):B[_M]=C[_M]
		if A.get(CONF_LED_MODE):B[CONF_LED_MODE]=A[CONF_LED_MODE]
		if C.get(CONF_TARGET_BRIGHTNESS):B[CONF_TARGET_BRIGHTNESS]=int(C[CONF_TARGET_BRIGHTNESS])
		if C.get(CONF_TARGET_COLOR_TEMP):B[CONF_TARGET_COLOR_TEMP]=int(C[CONF_TARGET_COLOR_TEMP])
		if C.get(CONF_ENTITY_SETTINGS):B[CONF_ENTITY_SETTINGS]=C[CONF_ENTITY_SETTINGS]
		if A.get(_Q):B[_Q]=_B
		H=A.get(_A7,{});I=A.get(_f,{});J=A.get(_g,{})
		if D is not _A or H or I or J:B[_h]={K:D or{},_A7:H,_f:I,_g:J}
		F.append(B)
	return F
_SCENE_GROUPS={}
import re as _re
def _iter_lutron_bridges(hass):
	D='bridge';from homeassistant.config_entries import ConfigEntryState as F
	for C in hass.config_entries.async_entries(_R):
		if C.state is not F.LOADED:continue
		E=getattr(C,'runtime_data',_A)
		if E is not _A:
			A=getattr(E,D,_A)
			if A is not _A:yield A;continue
		B=hass.data.get(_R,{}).get(C.entry_id)
		if B is not _A:
			A=getattr(B,D,_A)
			if A is _A and isinstance(B,dict):A=B.get(D)
			if A is not _A:yield A
_RAISE_RL_RE=_re.compile('\\braise\\b',_re.IGNORECASE)
_LOWER_RL_RE=_re.compile('\\blower\\b',_re.IGNORECASE)
async def _auto_refresh_button_layout(hass,entry):
	K=hass;A=entry;R=bool(A.data.get(_i));e=_S in A.data
	if R and e:return
	B=str(A.data.get(CONF_DEVICE_SERIAL,'')).strip();G=str(A.data.get(_F,'')).strip();f=A.data.get(CONF_AREA_NAME,'');g=A.data.get(CONF_DEVICE_NAME,'')
	if not B:return
	from.const import KEYPAD_LAYOUTS as S,KEYPAD_GENERIC as T;from.config_flow import _infer_keypad_type as h;U=A.data.get(_AJ,'');V=h(U)if U else A.data.get(CONF_KEYPAD_TYPE,T);l,W=S.get(V,S[T])
	if R:
		for L in _iter_lutron_bridges(K):
			try:O=L.get_devices()
			except Exception as P:_LOGGER.debug("get_devices() failed backfilling model for '%s': %s",A.title,P);continue
			for F in O.values():
				if B and str(F.get(_K,''))==B or G and str(F.get(_F,''))==G:I=F.get(_T,'')or'';K.config_entries.async_update_entry(A,data={**A.data,_S:I});_LOGGER.debug("Backfilled model_number=%r for '%s'",I,A.title);return
		_LOGGER.debug("Could not backfill model_number for '%s' (serial=%s)",A.title,B);return
	def i(full_name,area,dev):
		C=full_name;A=C.strip()
		for B in[f"{area} {dev}",dev,area]:
			B=B.strip()
			if B and A.lower().startswith(B.lower()):A=A[len(B):].strip();break
		return A.title()if A else C.strip()
	for L in _iter_lutron_bridges(K):
		X=getattr(L,_U,_A)or{}
		if not X:continue
		Y=[A for A in X.values()if B and str(A.get(_K,''))==B or G and str(A.get('parent_device',''))==G]
		if not Y:continue
		H=[];C=_A;D=_A;Z={};Q=[]
		for M in Y:
			a=M.get(_A8)
			if a is _A:continue
			try:J=int(a)
			except(TypeError,ValueError):continue
			N=M.get('button_name')or M.get(_G,'');b=N.lower();j=M.get('button_led')is not _A
			if W:
				if b.endswith((' raise','-raise',' up','-up'))or _RAISE_RL_RE.search(N):C=J
				elif b.endswith((' lower','-lower',' down','-down'))or _LOWER_RL_RE.search(N):D=J
				elif not j:Q.append(J)
			H.append(J);c=i(N,f,g)
			if c:Z[str(J)]=c
		if W:
			for E in sorted(Q):
				if E%2==1 and C is _A:C=E
				elif E%2==0 and D is _A:D=E
			for E in sorted(Q):
				if C is _A and E!=D:C=E
				elif D is _A and E!=C:D=E
		H=sorted(set(H));d=[A for A in H if A not in(C,D)];I=''
		try:
			O=L.get_devices()
			for F in O.values():
				if B and str(F.get(_K,''))==B or G and str(F.get(_F,''))==G:I=F.get(_T,'')or'';break
		except Exception as P:_LOGGER.debug("get_devices() failed fetching model for '%s': %s",A.title,P)
		k={_i:H,_A9:d,_AA:C,_AB:D,_r:Z,_s:{},CONF_KEYPAD_TYPE:V,_S:I};_LOGGER.info("Auto-detected layout for '%s' (serial=%s): %d buttons, configurable=%s raise=%s lower=%s",A.title,B,len(H),d,C,D);K.config_entries.async_update_entry(A,data={**A.data,**k});return
	_LOGGER.warning("Could not auto-detect button layout for '%s' (serial=%s) — bridge not found or carries no button data.",A.title,B)
async def _find_led_entities(hass,config_entry):
	B=config_entry;E=str(B.data.get(CONF_DEVICE_SERIAL,'')).strip();H=str(B.data.get(_F,'')).strip();_LOGGER.debug("LED discovery starting for '%s' — serial=%s device_id=%s",B.title,E,H);J=dr.async_get(hass);N=er.async_get(hass);_LOGGER.debug('LED discovery: %d devices in registry',len(J.devices));C=_A
	for F in J.devices.values():
		for(O,P,*Q)in F.identifiers:
			if O!=_R:continue
			L=str(P).strip()
			if E and L==E or H and L==H:C=F;break
		if C:break
	if C is _A:
		_LOGGER.warning('LED discovery: no lutron_caseta device matched serial=%s device_id=%s. Dumping all device identifiers:',E,H)
		for F in J.devices.values():_LOGGER.warning("  Device '%s': identifiers=%s",F.name,list(F.identifiers))
		return{}
	K=er.async_entries_for_device(N,C.id);_LOGGER.debug("LED discovery: found lutron device '%s' (id=%s) with %d entities: %s",C.name,C.id,len(K),[(A.entity_id,A.domain,A.unique_id)for A in K]);G={}
	for A in K:
		if A.domain!=_P:continue
		I=' '.join(filter(_A,[A.name,A.original_name,A.unique_id])).lower();_LOGGER.debug("LED discovery: switch entity %s — haystack='%s'",A.entity_id,I)
		if'led'not in I:continue
		M=_re.search('button[_\\s]+(\\d+)[_\\s]+led',I)
		if M:D=int(M.group(1));G[D]=A.entity_id;_LOGGER.debug('LED discovery: button %d → %s',D,A.entity_id)
		else:
			D=_extract_btn_num_from_led_uid(A.unique_id or'',E)
			if D is not _A:G[D]=A.entity_id;_LOGGER.debug('LED discovery (lenient): button %d → %s (uid=%s)',D,A.entity_id,A.unique_id)
			else:_LOGGER.warning("LED discovery: '%s' contains 'led' but no button number could be extracted — haystack='%s'",A.entity_id,I)
	if G:_LOGGER.info("LED discovery for '%s': %s",B.title,G)
	else:_LOGGER.warning("LED discovery for '%s': no LED entities mapped (keypad_type=%s). If your keypad has LEDs, configure led_entity manually in the options flow, or check the debug_leds service output.",B.title,B.data.get(_t))
	return G
def _extract_button_number(btn_entry,hass):
	C=btn_entry;B=C.unique_id or'';G=C.entity_id or'';A=_re.search('_(\\d+)$',B)
	if A:return int(A.group(1))
	A=_re.search('button[_\\s](\\d+)',B.lower())
	if A:return int(A.group(1))
	D=hass.states.get(G)
	if D:
		for H in(_A8,_AC,'button_index'):
			E=D.attributes.get(H)
			if E is not _A:
				try:return int(E)
				except(ValueError,TypeError):pass
	F=_re.findall('\\d+',B)
	if F:return int(F[-1])
def _extract_btn_num_from_led_uid(uid,serial=''):
	B=serial
	if not uid:return
	A=uid
	if B and A.startswith(B+'_'):A=A[len(B)+1:]
	A=_re.sub('(?:^led[_-]|[_-]led$)','',A).strip('_-');C=_re.fullmatch('\\d+',A)
	if C:return int(C.group(0))
	D=_re.findall('\\d+',A)
	if D:return int(D[-1])
def _slug_us(s):return _re.sub('_+','_',_re.sub('[^a-z0-9]+','_',(s or'').lower())).strip('_')
def _resolve_led_btn_num(base,button_names):
	C=button_names;D=base.lower();E=_re.search('button[_\\s]*(\\d+)$',D)
	if E:return int(E.group(1))
	if C:
		F='_'+D;A=_A
		for(G,H)in C.items():
			B=_slug_us(H)
			if not B or not F.endswith('_'+B):continue
			try:I=int(G)
			except(ValueError,TypeError):continue
			if A is _A or len(B)>A[1]:A=I,len(B)
		if A is not _A:return A[0]
def _find_lutron_device(hass,config_entry):
	F=config_entry;B=str(F.data.get(CONF_DEVICE_SERIAL,'')).strip();C=F.data.get(CONF_DEVICE_NAME,'').strip().lower();D=dr.async_get(hass)
	for A in D.devices.values():
		for E in A.identifiers:
			if len(E)>=2 and E[0]==_R and str(E[1]).strip()==B:return A
	if C:
		for A in D.devices.values():
			if A.name and C in A.name.lower()and any(A[0]==_R for A in A.identifiers):_LOGGER.debug("LED: serial '%s' not matched; found device '%s' by name",B,A.name);return A
	G=[(A.name,list(A.identifiers))for A in D.devices.values()if any(A[0]==_R for A in A.identifiers)];_LOGGER.warning("LED discovery: no lutron_caseta device matched serial='%s' device_name='%s'. Available lutron_caseta devices: %s",B,C,G)
async def _find_led_entities_by_button_entities(hass,config_entry):
	O='button.';H=hass;D=config_entry;P=str(D.data.get(CONF_DEVICE_SERIAL,'')).strip();Q=er.async_get(H);I=_find_lutron_device(H,D)
	if I is _A:return{}
	M=er.async_entries_for_device(Q,I.id);J=[A for A in M if A.domain==_j];G=[A for A in M if A.domain==_P and A.entity_id.endswith('_led')];_LOGGER.debug("LED discovery for '%s': device '%s' has %d button entities, %d LED switch entities",D.title,I.name,len(J),len(G))
	if not G:_LOGGER.debug("LED discovery: no switch.*_led entities on device '%s'",I.name);return{}
	R={A.entity_id for A in G};B={};K=D.data.get(_r,{})or{}
	for E in J:
		F=E.entity_id[len(O):];L=f"switch.{F}_led"
		if L not in R:continue
		A=_resolve_led_btn_num(F,K)
		if A is _A:A=_extract_button_number(E,H)
		if A is not _A:B[A]=L;_LOGGER.debug("LED (A): button %d → '%s'",A,L)
	if B:_LOGGER.info("LED discovery for '%s' (strategy A): %s",D.title,B);return B
	N={A.unique_id:A for A in J if A.unique_id}
	for C in G:
		if not C.unique_id:continue
		E=N.get(C.unique_id)
		if E is _A:S=_re.sub('[_-]?led$','',C.unique_id).rstrip('_-');E=N.get(S)
		if E:
			F=E.entity_id[len(O):];A=_resolve_led_btn_num(F,K)
			if A is _A:A=_extract_button_number(E,H)
			if A is not _A:B[A]=C.entity_id;_LOGGER.debug("LED (B): button %d → '%s'",A,C.entity_id)
	if B:_LOGGER.info("LED discovery for '%s' (strategy B): %s",D.title,B);return B
	for C in G:
		F=C.entity_id[len('switch.'):];F=_re.sub('_led$','',F);A=_resolve_led_btn_num(F,K)
		if A is _A:A=_extract_btn_num_from_led_uid(C.unique_id or'',P)
		if A is not _A:B[A]=C.entity_id;_LOGGER.debug("LED (C): button %d → '%s'",A,C.entity_id)
	if B:_LOGGER.info("LED discovery for '%s' (strategy C): %s",D.title,B);return B
	_LOGGER.warning("LED discovery for '%s': all strategies failed. button entities=%s  LED entities=%s  Configure led_entity manually in options or run debug_leds service.",D.title,[A.entity_id for A in J],[A.entity_id for A in G]);return B
async def _async_debug_leds(hass,call):
	C=hass;A=[];J=C.data.get(DOMAIN,{}).get(_u,{})
	if not J:A.append('No entry controllers found in hass.data — is the integration loaded?')
	for(R,B)in J.items():
		A.append(f"\n{"="*60}");A.append(f"Keypad : {B.name}");A.append(f"Serial : {B.serial}");A.append(f"device_id: {B.device_id}");A.append(f"LED map (auto-discovered): {B._led_map}");A.append(f"Button switches registered: {list(B._button_switches.keys())}")
		for(F,K)in B._buttons.items():
			O=K.get(CONF_ACTION_TYPE,_k);L=K.get(CONF_LED_ENTITY,'');M=B._led_map.get(F,'');G=L or M;A.append(f"\n  Button {F}  action={O}");A.append(f"    manual led_entity : '{L}'");A.append(f"    auto-discovered   : '{M}'");A.append(f"    resolved LED      : '{G}'")
			if G:D=C.states.get(G);A.append(f"    LED entity state  : {D.state if D else"⚠ ENTITY NOT FOUND"}")
			else:A.append('    ⚠ NO LED ENTITY — auto-discovery failed and no manual led_entity set')
			H=B._button_switches.get(F);A.append(f"    HA switch state   : {"ON"if H and H.is_on else"OFF"}{""if H else"  ⚠ switch entity not registered"}")
	A.append(f"\n{"="*60}");A.append("All switch entities with 'led' in entity_id:")
	for D in C.states.async_all(_P):
		if'led'in D.entity_id.lower():A.append(f"  {D.entity_id}: {D.state}")
	A.append("\nDevice registry — devices with 'lutron' identifiers:");P=dr.async_get(C)
	for I in P.devices.values():
		if any('lutron'in str(A).lower()for A in I.identifiers):A.append(f"  '{I.name}'  identifiers={list(I.identifiers)}")
	A.append('\nEntity registry — lutron_caseta switch entities:');Q=er.async_get(C)
	for E in Q.entities.values():
		if E.domain==_P and E.platform==_R:A.append(f"  {E.entity_id}  unique_id={E.unique_id}  device_id={E.device_id}")
	N='\n'.join(A);_LOGGER.warning('LED DEBUG REPORT:\n%s',N);C.bus.async_fire('lutron_keypad_controller_debug',{'report':N})
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/get_entries"})
@websocket_api.async_response
async def _ws_get_entries(hass,connection,msg):
	B=[]
	for A in hass.config_entries.async_entries(DOMAIN):
		if A.data.get(_O):continue
		B.append({_L:A.entry_id,'title':A.title,_V:dict(A.data),'options':dict(A.options),'state':A.state.value})
	connection.send_result(msg[_E],B)
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/save_keypad_config",vol.Required(_L):str,vol.Required(_U):dict})
@websocket_api.async_response
async def _ws_save_keypad_config(hass,connection,msg):
	E=connection;B=msg;A=hass;D=B[_L];F=B[_U];C=A.config_entries.async_get_entry(D)
	if C is _A or C.domain!=DOMAIN:E.send_error(B[_E],_l,f"Entry '{D}' not found");return
	A.config_entries.async_update_entry(C,options={**C.options,_U:F});A.async_create_task(A.config_entries.async_reload(D));E.send_result(B[_E],{_Z:_B})
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/discover_keypads"})
@websocket_api.async_response
async def _ws_discover_keypads(hass,connection,msg):
	I='area';C=hass;from.config_flow import _infer_keypad_type as J,LUTRON_TYPE_MAP as K;E={str(A.data.get(CONF_DEVICE_SERIAL,''))for A in C.config_entries.async_entries(DOMAIN)};D=[]
	for L in _iter_lutron_bridges(C):
		try:M=L.get_devices()
		except Exception as N:_LOGGER.debug('get_devices() failed during discovery: %s',N);continue
		for B in M.values():
			F=str(B.get(_K,''))
			if not F or F in E:continue
			G=B.get(_D,'')
			if G not in K:continue
			D.append({_K:F,_G:B.get(_G,''),I:B.get(_AD,''),_D:G,_t:J(G),_T:B.get(_T,'')or'',_F:str(B.get(_F,''))})
	from.config_flow import _discover_lip_keypads as O
	for H in await O(C):
		A=H[_V]
		if A[CONF_DEVICE_SERIAL]in E:continue
		D.append({_K:A[CONF_DEVICE_SERIAL],_G:A[_G],I:A.get(CONF_AREA_NAME,''),_D:A.get(_S,'')or'lutron_lip',_t:A[CONF_KEYPAD_TYPE],_T:A.get(_S,''),_F:A[_F]})
	from.config_flow import _discover_rfwc5_keypads as P
	for H in P(C):
		A=H[_V]
		if A[CONF_DEVICE_SERIAL]in E:continue
		D.append({_K:A[CONF_DEVICE_SERIAL],_G:A[_G],I:A.get(CONF_AREA_NAME,''),_D:'Eaton RFWC5',_t:A[CONF_KEYPAD_TYPE],_T:'RFWC5',_F:A[_F]})
	connection.send_result(msg[_E],D)
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/add_keypad",vol.Required(_K):str,vol.Required(_G):str,vol.Optional(_F,default=''):str})
@websocket_api.async_response
async def _ws_add_keypad(hass,connection,msg):
	S='flow_error';R='result';Q='create_entry';P='panel';K='reason';F=hass;D=connection;B=msg;from.config_flow import _infer_keypad_type as W,_detect_button_layout as X;C=B[_K];H=(B.get(_G)or C).strip();L=B.get(_F,'')
	if C.startswith('lip_'):
		from.config_flow import _discover_lip_keypads as Y;I=next((A for A in await Y(F)if A[_V][CONF_DEVICE_SERIAL]==C),_A)
		if I is _A:D.send_error(B[_E],_l,f"lip keypad '{C}' not found");return
		J={**I[_V],_G:H,CONF_DEVICE_NAME:H};A=await F.config_entries.flow.async_init(DOMAIN,context={_v:P},data=J)
		if A.get(_D)==Q:E=A.get(R);D.send_result(B[_E],{_Z:_B,_L:E.entry_id if E else''})
		else:D.send_error(B[_E],A.get(K,S),f"Could not add keypad: {A.get(K,_W)}")
		return
	if C.startswith('rfwc5_'):
		from.config_flow import _discover_rfwc5_keypads as Z;I=next((A for A in Z(F)if A[_V][CONF_DEVICE_SERIAL]==C),_A)
		if I is _A:D.send_error(B[_E],_l,f"RFWC5 keypad '{C}' not found");return
		J={**I[_V],_G:H,CONF_DEVICE_NAME:H};A=await F.config_entries.flow.async_init(DOMAIN,context={_v:P},data=J)
		if A.get(_D)==Q:E=A.get(R);D.send_result(B[_E],{_Z:_B,_L:E.entry_id if E else''})
		else:D.send_error(B[_E],A.get(K,S),f"Could not add keypad: {A.get(K,_W)}")
		return
	M=N=O=T=''
	for a in _iter_lutron_bridges(F):
		try:b=a.get_devices()
		except Exception:continue
		for G in b.values():
			if str(G.get(_K,''))==C:M=G.get(_D,'');N=G.get(_AD,'');O=G.get(_G,'');T=G.get(_T,'')or'';L=str(G.get(_F,''))or L;break
		if M:break
	U=W(M);c=X(F,C,U,device_name=O,area_name=N,device_id=L);J={_G:H,CONF_DEVICE_SERIAL:C,CONF_DEVICE_NAME:O,CONF_AREA_NAME:N,CONF_KEYPAD_TYPE:U,_AJ:M,_S:T,_F:L,**c};A=await F.config_entries.flow.async_init(DOMAIN,context={_v:P},data=J)
	if A.get(_D)==Q:E=A.get(R);D.send_result(B[_E],{_Z:_B,_L:E.entry_id if E else''})
	elif A.get(_D)=='abort':V=A.get(K,_W);D.send_error(B[_E],V,f"Could not add keypad: {V}")
	else:D.send_error(B[_E],S,'Unexpected flow result')
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/delete_keypad",vol.Required(_L):str})
@websocket_api.async_response
async def _ws_delete_keypad(hass,connection,msg):
	C=connection;A=msg;B=A[_L];D=hass.config_entries.async_get_entry(B)
	if D is _A or D.domain!=DOMAIN:C.send_error(A[_E],_l,f"Entry '{B}' not found");return
	await hass.config_entries.async_remove(B);C.send_result(A[_E],{_Z:_B})
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/license_status",vol.Optional(_L):str})
@websocket_api.async_response
async def _ws_license_status(hass,connection,msg):
	Y='last_check';X='warn_only';W='max_version';V='bound_instance';U='binding';T='expires_at';N=connection;M='loaded';L='has_key';H='error';G='valid';A=hass;from.license import LicenseError as Z,load_license_cache as a,validate_license_offline as b;D=_controller_entry(A)
	if D is _A:O=A.config_entries.async_entries(DOMAIN);D=O[0]if O else _A
	c=await async_get_instance_id(A);C={'instance_id':c,L:_C,G:_C,M:_C,H:_A}
	if D is _A:N.send_result(msg[_E],C);return
	C[_L]=D.entry_id;C[M]=D.state.value==M;d=await async_get_integration(A,DOMAIN);e=str(d.version);P=await a(A);from.backends import get_backend as f;from.license import EXPECTED_PRODUCT as Q;g={'lutron_keypad_controller':'Lutron (Caséta / QS / RA)','rfwc5_controller':'Eaton RFWC5 (Z-Wave)'};R={Q}
	for S in A.config_entries.async_entries(DOMAIN):
		if not S.data.get(_O):R.add(f(S).license_product)
	I=[]
	for E in sorted(R):
		J=await _license_key_for_product(A,E);F={_w:E,'label':g.get(E,E),L:bool(J),G:_C,H:_A}
		if J:
			try:
				B=b(J,current_version=e,expected_product=E);F.update({G:_B,_x:B.jti,T:B.expires_at,U:B.binding,V:B.instance_id,W:B.max_version,X:B.warn_only})
				if P.get(_x)==B.jti:F[Y]=P.get('last_ok')
			except Z as h:F[H]=str(h)
		I.append(F)
	C['modules']=I;K=next((A for A in I if A[_w]==Q),_A)
	if K:C.update({A:K[A]for A in(L,G,H,_x,T,U,V,W,X,Y)if A in K})
	N.send_result(msg[_E],C)
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/set_license",vol.Required(_L):str,vol.Required(_a):str,vol.Optional(_w):str})
@websocket_api.async_response
async def _ws_set_license(hass,connection,msg):
	E=connection;C=msg;A=hass;from.license import EXPECTED_PRODUCT as F;B=_controller_entry(A)
	if B is _A:B=A.config_entries.async_get_entry(C[_L])
	if B is _A or B.domain!=DOMAIN:E.send_error(C[_E],_l,'Entry not found');return
	G=(C.get(_w)or F).strip();H=C[_a].strip();D={**B.options};I={**(D.get(_m)or{})};I[G]=H;D[_m]=I
	if G==F:D[_a]=H
	A.config_entries.async_update_entry(B,options=D)
	for J in A.config_entries.async_entries(DOMAIN):
		if not J.data.get(_O):A.async_create_task(A.config_entries.async_reload(J.entry_id))
	E.send_result(C[_E],{_Z:_B})
async def _register_panel_once(hass):
	C='_panel_registered';A=hass
	if A.data.get(DOMAIN,{}).get(C):return
	B=_COMPONENT_DIR/'frontend'/'lutron_panel.js'
	try:from homeassistant.components.http import StaticPathConfig as D;await A.http.async_register_static_paths([D(_AE,str(B),cache_headers=_C)])
	except(AttributeError,ImportError):
		try:A.http.register_static_path(_AE,str(B),cache_headers=_C)
		except Exception as E:_LOGGER.warning('Could not register static path for panel: %s',E)
	websocket_api.async_register_command(A,_ws_get_entries);websocket_api.async_register_command(A,_ws_save_keypad_config);websocket_api.async_register_command(A,_ws_discover_keypads);websocket_api.async_register_command(A,_ws_add_keypad);websocket_api.async_register_command(A,_ws_delete_keypad);websocket_api.async_register_command(A,_ws_license_status);websocket_api.async_register_command(A,_ws_set_license);A.data.setdefault(DOMAIN,{})[C]=_B;A.data[DOMAIN][_AF]=await _load_sidebar_show(A);_update_sidebar_panel(A)
@callback
def async_set_sidebar(hass,show):hass.data.setdefault(DOMAIN,{})[_AF]=bool(show);_update_sidebar_panel(hass)
@callback
def _update_sidebar_panel(hass):
	F='lutron-keypads';E='_sidebar_shown';D='_panel_registered_url';C=hass;A=C.data.setdefault(DOMAIN,{});B=bool(A.get(_AF))
	if A.get(D)and A.get(E)==B:return
	if A.get(D):
		try:frontend.async_remove_panel(C,F)
		except Exception:pass
	try:frontend.async_register_built_in_panel(C,component_name='custom',sidebar_title='Lutron Keypads'if B else _A,sidebar_icon='mdi:keyboard-outline'if B else _A,frontend_url_path=F,config={'_panel_custom':{_G:'lutron-keypad-panel','module_url':_AE}},require_admin=_B);A[D]=_B;A[E]=B
	except Exception as G:_LOGGER.warning('Could not register Lutron Keypads panel: %s',G)
_SIDEBAR_STORE_KEY='lutron_keypad_controller_sidebar'
async def _load_sidebar_show(hass):from homeassistant.helpers.storage import Store;A=Store(hass,1,_SIDEBAR_STORE_KEY);B=await A.async_load()or{};return bool(B.get('show',_C))
async def _save_sidebar_show(hass,show):from homeassistant.helpers.storage import Store;A=Store(hass,1,_SIDEBAR_STORE_KEY);await A.async_save({'show':bool(show)})
_TRAVEL_STORE_KEY='lutron_keypad_controller_travel'
_DEFAULT_TRAVEL_S=3e1
_TRAVEL_SIGNAL='lutron_keypad_controller_travel_updated'
async def _load_travel(hass):from homeassistant.helpers.storage import Store;B=Store(hass,1,_TRAVEL_STORE_KEY);A=await B.async_load()or{};return{_b:float(A.get(_b)or _DEFAULT_TRAVEL_S),_X:dict(A.get(_X)or{})}
async def _save_travel(hass):from homeassistant.helpers.storage import Store;B=Store(hass,1,_TRAVEL_STORE_KEY);A=hass.data.setdefault(DOMAIN,{}).get(_y)or{};await B.async_save({_b:float(A.get(_b)or _DEFAULT_TRAVEL_S),_X:dict(A.get(_X)or{})})
@callback
def _cover_travel_time(hass,cover_id):
	B=hass.data.get(DOMAIN,{}).get(_y)or{};A=(B.get(_X)or{}).get(cover_id)
	if A and float(A)>0:return float(A)
	return float(B.get(_b)or _DEFAULT_TRAVEL_S)
@callback
def _discover_cover_cycle_covers(hass):
	E=set()
	for A in hass.config_entries.async_entries(DOMAIN):
		if A.data.get(_O):continue
		B=A.options.get(_U)or A.data.get(_U)or{};F=B.values()if isinstance(B,dict)else B
		for C in F:
			if not isinstance(C,dict)or C.get(CONF_ACTION_TYPE)!=ACTION_COVER_CYCLE:continue
			for D in _normalize_targets(C.get(CONF_ACTION_TARGET,[])):
				if isinstance(D,str)and D.startswith('cover.'):E.add(D)
	return sorted(E)
async def _calibrate_shade_travel(hass,cover_id):
	I='lutron_calibrate';H='Lutron Keypad Controller';B=cover_id;A=hass;from homeassistant.helpers.dispatcher import async_dispatcher_send as S;from homeassistant.components.persistent_notification import async_create as F;M=A.data.setdefault(DOMAIN,{});J=M.setdefault('_calibrating',set())
	if B in J:return
	J.add(B);D=5.;N=3.;O=_cover_travel_time(A,B)+6.;K=A.states.get(B);E=K.name if K is not _A and K.name else B
	async def G(service):await A.services.async_call(_z,service,{ATTR_ENTITY_ID:B},blocking=_B)
	F(A,f"Calibrating '{E}'. It will close, open briefly, then close again (~{int(O+D+N)}s) — please don't operate it meanwhile.",title=H,notification_id=I)
	try:
		await G(_A0);await asyncio.sleep(O);await G(_AG);await asyncio.sleep(D);await G(_AK);await asyncio.sleep(N);P=A.states.get(B);C=P.attributes.get(_AL)if P is not _A else _A
		if not C or float(C)<=0:F(A,f"Calibration of '{E}' failed — no movement detected (position={C}). Try again or set the travel time manually.",title=H,notification_id=I);return
		C=min(float(C),1e2);Q=D*1e2/C;L=int(round(min(max(Q,3.),18e1)))+1;T=M.setdefault(_y,{_b:_DEFAULT_TRAVEL_S,_X:{}});T.setdefault(_X,{})[B]=float(L);await _save_travel(A);S(A,_TRAVEL_SIGNAL);_LOGGER.info("Calibrated '%s': opened to %.0f%% in %.1fs → full travel ≈ %.1fs → travel time set to %ds",E,C,D,Q,L);F(A,f"Calibrated '{E}': reached {C:.0f}% in {int(D)}s → travel time set to {L}s.",title=H,notification_id=I);await G(_A0)
	except Exception as R:_LOGGER.warning("Calibration of '%s' errored: %s",B,R);F(A,f"Calibration of '{E}' errored: {R}",title=H,notification_id=I)
	finally:J.discard(B)
@callback
def _async_ensure_controller_entry(hass):
	A=hass
	if any(A.data.get(_O)for A in A.config_entries.async_entries(DOMAIN)):return
	A.async_create_task(A.config_entries.flow.async_init(DOMAIN,context={_v:_AM},data={}))
async def _async_setup_controller_entry(hass,entry):
	C=entry;A=hass;await _register_panel_once(A);A.data.setdefault(DOMAIN,{})[_y]=await _load_travel(A);await A.config_entries.async_forward_entry_setups(C,[_P,_A1,_j]);D=dr.async_get(A);B=D.async_get_device(identifiers={(DOMAIN,_AM)})
	if B is not _A:
		for E in list(B.config_entries):
			if E!=C.entry_id:D.async_update_device(B.id,remove_config_entry_id=E)
	return _B
@callback
def _controller_entry(hass):
	for A in hass.config_entries.async_entries(DOMAIN):
		if A.data.get(_O):return A
async def _global_license_key(hass):
	B=hass;C=_controller_entry(B)
	if C is not _A:
		A=(C.options.get(_a)or'').strip()
		if A:return A
	for D in B.config_entries.async_entries(DOMAIN):
		A=(D.options.get(_a)or'').strip()
		if A:return A
	return await recall_license_key(B)
async def _license_key_for_product(hass,product):
	B=product;A=hass;C=_controller_entry(A)
	if C is not _A:
		F=C.options.get(_m)or{};D=(F.get(B)or'').strip()
		if D:return D
	from.license import EXPECTED_PRODUCT as G
	if B==G:
		E=await _global_license_key(A)
		if E:return E
	return await recall_license_key(A,B)
async def async_setup(hass,config):
	B=config;A=hass;A.data.setdefault(DOMAIN,{});await _register_panel_once(A)
	if DOMAIN not in B:return _B
	E=B[DOMAIN].get('keypads',[]);C=[]
	for F in E:D=LutronKeypadsController(A,F);C.append(D);D.async_register()
	A.data[DOMAIN][_A2]=C;A.services.async_register(DOMAIN,_AH,_async_debug_leds);return _B
async def async_setup_entry(hass,entry):
	B=hass;A=entry;B.data.setdefault(DOMAIN,{})
	if A.data.get(_O):return await _async_setup_controller_entry(B,A)
	K=B.data[DOMAIN].setdefault('_reload_listeners',set())
	if A.entry_id not in K:A.add_update_listener(_async_reload_entry);K.add(A.entry_id)
	await _register_panel_once(B);_async_ensure_controller_entry(B);from.backends import get_backend as Q;E=Q(A).license_product;F=await _license_key_for_product(B,E)
	if not F:_LOGGER.error("Ctrlable Keypad Controller: no license for module '%s'. Open the panel's License dialog and paste a license for this module (obtain one from portal.ctrlable.com).",E);return _C
	R=await async_get_integration(B,DOMAIN);S=str(R.version)
	try:D=validate_license_offline(F,current_version=S,expected_product=E)
	except LicenseError as T:_LOGGER.error("Ctrlable Keypad Controller: license validation failed for module '%s' — %s",E,T);return _C
	if D.warn_only:_LOGGER.warning('Ctrlable Lutron Keypad: license has expired but warn_only mode is active. Please renew your license.')
	G=await async_get_instance_id(B)
	if D.binding=='instance'and D.instance_id and D.instance_id!=G:_LOGGER.error('Ctrlable Lutron Keypad: license is bound to instance %s; this HA is %s.',D.instance_id,G);return _C
	L=await check_revocation_online(D.jti,instance_id=G)
	if L is _C:_LOGGER.error('Ctrlable Lutron Keypad: license rejected by portal. Aborting setup.');return _C
	M=await load_license_cache(B);N=M.get('last_ok')if M.get(_x)==D.jti else _A
	if L is _B:await save_license_cache(B,D.jti)
	elif N is not _A:
		O=(time.time()-N)/86400
		if O>30:_LOGGER.warning('Ctrlable Lutron Keypad: portal unreachable for %.0f days. Ensure this device can reach portal.ctrlable.com periodically.',O)
	await remember_license_key(B,F,E);C=_controller_entry(B)
	if C is not _A:
		H={**C.options};I={**(C.options.get(_m)or{})}
		if I.get(E)!=F:I[E]=F;H[_m]=I
		from.license import EXPECTED_PRODUCT as U
		if E==U:H[_a]=F
		if H!=dict(C.options):B.config_entries.async_update_entry(C,options=H)
	B.data.setdefault(DOMAIN,{});B.data[DOMAIN].setdefault(_A2,[]);B.data[DOMAIN].setdefault(_u,{});await _auto_refresh_button_layout(B,A)
	if not A.data.get(_i)or _S not in A.data:
		async def P(_event=_A):await _auto_refresh_button_layout(B,A)
		if B.state is CoreState.running:B.async_create_task(P())
		else:A.async_on_unload(B.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED,P))
	J=_build_buttons_from_options(A.options.get(_U,{}));V={_G:A.title,CONF_DEVICE_SERIAL:A.data.get(CONF_DEVICE_SERIAL,''),CONF_DEVICE_NAME:A.data.get(CONF_DEVICE_NAME,''),CONF_AREA_NAME:A.data.get(CONF_AREA_NAME,''),CONF_KEYPAD_TYPE:A.data.get(CONF_KEYPAD_TYPE,_A6),_F:A.data.get(_F,''),_i:A.data.get(_i,[]),_A9:A.data.get(_A9,[]),_AA:A.data.get(_AA),_AB:A.data.get(_AB),_r:A.data.get(_r,{}),_s:A.data.get(_s,{}),CONF_BUTTONS:J};C=LutronKeypadsController(B,V,config_entry=A)
	if J:C.async_register();_LOGGER.info("Keypad '%s' loaded from UI options with %d button(s)",A.title,len(J))
	else:_LOGGER.info("Keypad '%s' loaded (no buttons configured yet). Click the gear icon to configure buttons, or add YAML under lutron_keypad_controller:",A.title)
	B.data[DOMAIN][_u][A.entry_id]=C;B.data[DOMAIN][_A2].append(C)
	if not B.services.has_service(DOMAIN,_AH):B.services.async_register(DOMAIN,_AH,_async_debug_leds)
	await C.async_initialize();await _cleanup_orphaned_entities(B,A);await B.config_entries.async_forward_entry_setups(A,PLATFORMS);B.async_create_background_task(periodic_revocation_check(B,D.jti,A.entry_id,instance_id=G),name=f"lutron_keypad_license_check_{A.entry_id}");return _B
async def _cleanup_orphaned_entities(hass,entry):
	D=entry;B=er.async_get(hass)
	for A in er.async_entries_for_config_entry(B,D.entry_id):
		C=A.unique_id
		if any(f"_entity_{A}"in C for A in('2','3','4')):B.async_remove(A.entity_id);_LOGGER.info('Removed orphaned multi-slot entity: %s',A.entity_id)
		elif A.entity_id.startswith('text.')and any(C.endswith(A)for A in('_entity_1','_led','_scene_group')):B.async_remove(A.entity_id);_LOGGER.info('Removed old text entity (now a sensor): %s',A.entity_id)
		elif A.entity_id.startswith('switch.')and C.endswith('_enabled'):B.async_remove(A.entity_id);_LOGGER.info('Removed old enabled-toggle switch (now LED switch): %s',A.entity_id)
		elif C in(f"{D.entry_id}_show_in_sidebar",f"{DOMAIN}_show_in_sidebar"):B.async_remove(A.entity_id);_LOGGER.info('Removed old sidebar switch: %s',A.entity_id)
async def async_unload_entry(hass,entry):
	B=entry;A=hass
	if B.data.get(_O):return await A.config_entries.async_unload_platforms(B,[_P,_A1,_j])
	D=await A.config_entries.async_unload_platforms(B,PLATFORMS);C=A.data[DOMAIN].get(_u,{}).pop(B.entry_id,_A)
	if C is not _A:
		C.async_unregister()
		try:A.data[DOMAIN][_A2].remove(C)
		except ValueError:pass
	return D
async def _async_reload_entry(hass,entry):await hass.config_entries.async_reload(entry.entry_id)
def _normalize_led_map(raw_led_map,config_entry):
	C=config_entry;A=raw_led_map
	if not A:return A
	F=C.data;D=get_button_list(F.get(CONF_KEYPAD_TYPE,KEYPAD_GENERIC));G={A[_A1]for A in D}
	if any(A in G for A in A):return A
	H=sorted(A[_A1]for A in D if not A['is_raise']and not A['is_lower']);E=sorted(A.keys());B={}
	for(I,J)in zip(H,E):B[I]=A[J]
	_LOGGER.info("'%s': LED map: LEAP global IDs %s → sequential button numbers %s",C.title,E,list(B.keys()));return B
class LutronKeypadsController:
	def __init__(A,hass,config,config_entry=_A):
		C=config_entry;B=config;A.hass=hass;A.name=B[_G];A.serial=str(B.get(CONF_DEVICE_SERIAL,'')).strip();A.device_id=str(B.get(_F,'')).strip();A.device_name=B.get(CONF_DEVICE_NAME,'').strip().lower();A.area_name=B.get(CONF_AREA_NAME,'').strip().lower();A.keypad_type=B.get(CONF_KEYPAD_TYPE,_A6);A.scene_group=B.get(_M,'').strip();A._config_entry=C;from.backends import get_backend as E;A._backend=E(C);A._buttons={}
		for D in B.get(CONF_BUTTONS,[]):A._buttons[D[CONF_BUTTON_NUMBER]]=D
		A._active_scene_btn=_A;A._last_action=_A;A._cover_states={};A._cover_cycle_mem={};A._light_dim_indices={};A._native_consumed=set();A._unsubscribe=_A;A._led_map={};A._button_switches={};A._leap_btn_map={}
		if C is not _A:F=C.data.get(_s,{});A._leap_btn_map={int(A):B for(A,B)in F.items()}
		A._press_times={};A._last_press_times={};A._last_dispatch_times={};A._held={};A._confirm_handles={};A._ramp_tasks={};A._ramp_dirs={};A._ramp_end_times={};A._state_sensors=[];A._entity_tracking_unsubs=[]
	@callback
	def async_register(self):A=self;A._unsubscribe=A._backend.subscribe(A.hass,A)
	@callback
	def async_unregister(self):
		A=self
		for B in A._entity_tracking_unsubs:B()
		A._entity_tracking_unsubs.clear()
		if A._unsubscribe is not _A:A._unsubscribe();A._unsubscribe=_A;_LOGGER.debug("Lutron Keypad Controller '%s' unregistered",A.name)
		for C in A._confirm_handles.values():C.cancel()
		A._confirm_handles.clear()
		for D in A._ramp_tasks.values():D.cancel()
		A._ramp_tasks.clear();A._press_times.clear();A._last_dispatch_times.clear();A._held.clear();A._ramp_end_times.clear()
	async def _build_leap_btn_map(A):
		if A._leap_btn_map:_LOGGER.debug("'%s': _build_leap_btn_map — using stored map %s",A.name,A._leap_btn_map);return
		E=_C
		for I in _iter_lutron_bridges(A.hass):
			E=_B;F=getattr(I,'button_devices',_A)or{}
			if not F:continue
			C=0
			for B in F.values():
				J=str(B.get(_K,''));K=str(B.get(_F,''))
				if J!=A.serial and K!=A.device_id:continue
				C+=1;D=_A
				for L in(_A8,_AC):
					G=B.get(L)
					if G is not _A:
						try:D=int(G);break
						except(TypeError,ValueError):pass
				H=B.get(_AC)
				if D is not _A and H is not _A:
					try:A._leap_btn_map[int(H)]=D
					except(TypeError,ValueError):pass
			if C>0:_LOGGER.debug("'%s': _build_leap_btn_map — matched %d entries on bridge, map=%s",A.name,C,A._leap_btn_map);return
		if not E:_LOGGER.warning("'%s': _build_leap_btn_map — no lutron_caseta bridge found; raise/lower LEAP remapping unavailable.",A.name)
		else:_LOGGER.debug("'%s': _build_leap_btn_map — no bridge had this serial in button_devices (expected for Caseta Pro).",A.name)
	async def async_initialize(A):
		if A._config_entry is _A:return
		await A._build_leap_btn_map();await A._backend.async_initialize(A.hass,A);A._led_map=await A._backend.async_find_leds(A.hass,A._config_entry)
		if A._led_map:_LOGGER.warning("'%s': LED map ready (keys = sequential button numbers): %s",A.name,A._led_map)
		else:_LOGGER.debug("'%s': no LED entities found (expected for CASETA Pro keypads without LED feedback). Call debug_leds service to diagnose.",A.name)
		A._setup_entity_state_tracking()
	def _get_led_entity(A,btn_num):B=btn_num;C=A._buttons.get(B,{}).get(CONF_LED_ENTITY,'');return C if C else A._led_map.get(B)
	def register_button_switch(A,btn_num,switch):
		B=btn_num;A._button_switches[B]=switch;C=A._buttons.get(B,{});E=C.get(CONF_ACTION_TYPE);D=_normalize_targets(C.get(CONF_ACTION_TARGET,[]))
		if D:
			if E==ACTION_ENTITY_TOGGLE:A._update_entity_toggle_led(B,C,D)
			elif E==ACTION_SINGLE_ACTION:A._update_scene_mode_led(B,D)
	@callback
	def _update_entity_toggle_led(self,btn_num,btn_cfg,entities):
		C=entities;B=btn_num;A=self;D=btn_cfg.get(CONF_LED_MODE,LED_MODE_ROOM)
		if D==LED_MODE_SCENE:A._update_scene_mode_led(B,C)
		elif D==LED_MODE_PATHWAY:A._update_pathway_mode_led(B,C)
		else:A._update_room_mode_led(B,C)
	@callback
	def _update_room_mode_led(self,btn_num,entities):B=btn_num;A=self;C=any((D:=A.hass.states.get(B))is not _A and D.state not in(_n,_o,_A3,_W,_k)for B in entities);A._update_button_switch_state(B,C);A.hass.async_create_task(A._write_led_entity(B,C))
	@callback
	def _update_pathway_mode_led(self,btn_num,entities):C=entities;B=btn_num;A=self;D=bool(C)and all((E:=A.hass.states.get(B))is not _A and E.state not in(_n,_o,_A3,_W,_k)for B in C);A._update_button_switch_state(B,D);A.hass.async_create_task(A._write_led_entity(B,D))
	@callback
	def _update_scene_mode_led(self,btn_num,entities):
		D=entities;B=btn_num;A=self;C=A._buttons.get(B,{});I=int(C.get(CONF_TARGET_BRIGHTNESS)or 0);J=int(C.get(CONF_TARGET_COLOR_TEMP)or 0);K=C.get(CONF_ENTITY_SETTINGS,{})
		def F(eid):
			D=eid;B=A.hass.states.get(D)
			if B is _A or B.state in(_n,_o,_A3,_W,_k):return _C
			if not D.startswith(_N):return _B
			E=K.get(D,{});F=int(E.get(_H)or I);G=int(E.get(_c)or J)
			if F>0:
				L=round((B.attributes.get(_H,0)or 0)/255*100)
				if abs(L-F)>5:return _C
			if G>0:
				C=B.attributes.get(_AI)
				if C is _A:
					H=B.attributes.get(_c)
					if H:C=round(1000000/H)
				if C is not _A and abs(int(C)-G)>100:return _C
			return _B
		E=bool(D)and all(F(A)for A in D);A._update_button_switch_state(B,E);A.hass.async_create_task(A._write_led_entity(B,E))
	def _setup_entity_state_tracking(A):
		for C in A._entity_tracking_unsubs:C()
		A._entity_tracking_unsubs.clear()
		for(D,E)in A._buttons.items():
			F=E.get(CONF_ACTION_TYPE)
			if F not in(ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION):continue
			B=_normalize_targets(E.get(CONF_ACTION_TARGET,[]))
			if not B:continue
			if F==ACTION_SINGLE_ACTION:
				@callback
				def G(event,_btn=D,_ents=B):A._update_scene_mode_led(_btn,_ents)
				C=async_track_state_change_event(A.hass,B,G);A._entity_tracking_unsubs.append(C);_LOGGER.debug("'%s': button %d: single_action scene LED tracking %s",A.name,D,B)
			else:
				H=E.get(CONF_LED_MODE,LED_MODE_ROOM)
				@callback
				def I(event,_btn=D,_cfg=E,_ents=B):A._update_entity_toggle_led(_btn,_cfg,_ents)
				C=async_track_state_change_event(A.hass,B,I);A._entity_tracking_unsubs.append(C);_LOGGER.debug("'%s': button %d: %s LED tracking %s",A.name,D,H,B)
	def register_state_sensor(A,sensor):
		B=sensor
		if B not in A._state_sensors:A._state_sensors.append(B)
	@callback
	def _notify_state_sensors(self):
		for A in self._state_sensors:A.async_write_ha_state()
	def _update_button_switch_state(B,btn_num,is_on):
		A=B._button_switches.get(btn_num)
		if A is not _A:A.update_led_state(is_on)
	async def _write_led_entity(A,btn_num,is_on):
		C=is_on;B=btn_num;D=A._get_led_entity(B)
		if not D:return
		E=A._buttons.get(B,{})
		if E.get(CONF_LED_INVERT,_C):C=not C
		try:await A._backend.async_write_led(A.hass,D,C);_LOGGER.debug("'%s': button %d LED '%s' → %s",A.name,B,D,'ON'if C else'OFF')
		except Exception as F:_LOGGER.warning("'%s': button %d could not write LED entity '%s': %s",A.name,B,D,F)
	async def _write_group_leds(A,active_btn,active_btn_cfg):
		C=active_btn_cfg.get(_M)or A.scene_group
		for(B,D)in A._buttons.items():
			if D.get(CONF_ACTION_TYPE)!=ACTION_STATEFUL_SCENE:continue
			if not A._get_led_entity(B):continue
			E=D.get(_M)or A.scene_group
			if C and E!=C:continue
			await A._write_led_entity(B,B==active_btn)
	async def _sync_leds(A,active_btn):
		C=active_btn;_LOGGER.debug("'%s': _sync_leds called, active_btn=%s",A.name,C)
		for(B,E)in A._buttons.items():
			if E.get(CONF_ACTION_TYPE)!=ACTION_STATEFUL_SCENE:continue
			if A._get_led_entity(B):continue
			D=B==C;_LOGGER.debug("'%s': Button %d (no LED entity) should_be_on=%s",A.name,B,D);A._update_button_switch_state(B,D)
	def _try_auto_map_raise_lower(B,leap_num):
		C=leap_num;from.const import RAISE_LOWER_BUTTON_TYPES as D
		for(E,F)in((ACTION_RAISE,D['raise']),(ACTION_LOWER,D['lower'])):
			if C not in F:continue
			A=next((A for(A,B)in B._buttons.items()if B.get(CONF_ACTION_TYPE)==E),_A)
			if A is not _A:B._leap_btn_map[C]=A;_LOGGER.info("'%s': auto-mapped raise/lower: leap_btn=%d → btn=%d (%s)",B.name,C,A,E);return A
	def _matches_event(A,event_data):
		B=event_data;C=str(B.get(_F,'')).strip()
		if C and A.device_id and C==A.device_id:return _B
		if A.serial:
			D=str(B.get(_K,'')).strip()
			if D and D==str(A.serial):return _B
		E=str(B.get('device_name','')).lower();F=str(B.get(_AD,'')).lower()
		if A.device_name and A.area_name:return E==A.device_name and F==A.area_name
		if A.device_name:return E==A.device_name
		if A.area_name:return F==A.area_name
		return _C
	@callback
	@callback
	def handle_button(self,source_btn,action):
		E=action;D=source_btn;A=self;B=A._leap_btn_map.get(int(D),int(D));C=A._buttons.get(B)
		if C is _A:
			F=A._try_auto_map_raise_lower(B)
			if F is not _A:B=F;C=A._buttons.get(B)
		if C is _A:_LOGGER.debug("'%s': button %d pressed but not configured — ignoring",A.name,B);return
		if A._backend.native_hold or A._backend.native_double_tap:A._handle_native_button(B,C,E);return
		if E=='release':A._handle_release(B);return
		_LOGGER.info("'%s': button %d (%s) pressed — action_type=%s",A.name,B,C.get(CONF_BUTTON_LABEL,''),C[CONF_ACTION_TYPE]);A._on_press(B,C)
	@callback
	def _handle_native_button(self,btn_num,btn_cfg,action):
		D=action;C=btn_cfg;B=btn_num;A=self
		if D=='press':A._held.pop(B,_A);A._native_consumed.discard(B);return
		if D==_g:_LOGGER.info("'%s': button %d HOLD (native)",A.name,B);A._native_consumed.add(B);A._on_hold_event(B);return
		if D==_f:
			_LOGGER.info("'%s': button %d DOUBLE TAP (native)",A.name,B);A._native_consumed.add(B);F=C.get(_h,{}).get(_f,{})
			if F.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE:G=A._merge_v2_block(C,F);A.hass.async_create_task(A._dispatch(B,G))
			else:A.hass.async_create_task(A._dispatch(B,C))
			return
		if A._held.pop(B,_C):
			E=A._ramp_tasks.pop(B,_A)
			if E is not _A and not E.done():E.cancel()
			A._ramp_end_times[B]=asyncio.get_event_loop().time()
		elif B not in A._native_consumed:_LOGGER.info("'%s': button %d TAP (native) — action_type=%s",A.name,B,C.get(CONF_ACTION_TYPE));A.hass.async_create_task(A._dispatch(B,C))
		A._native_consumed.discard(B)
	_HOLD_CONFIRM=.3;_HOLD_CONFIRM_CYCLE=.7;_PRESS_DEBOUNCE=.2;_DOUBLE_TAP_WINDOW=.4;_RAMP_STEP_PCT=10;_RAMP_INTERVAL=.4;_HOLD_ACTIONS=frozenset({ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION,ACTION_STATEFUL_SCENE,ACTION_RAISE,ACTION_LOWER,ACTION_LIGHT_CYCLE_DIM})
	@callback
	def _on_press(self,btn_num,btn_cfg):
		C=btn_cfg;B=btn_num;A=self;D=asyncio.get_event_loop().time();F=A._last_dispatch_times.get(B,0)
		if D-F<A._PRESS_DEBOUNCE:_LOGGER.debug("'%s': button %d press ignored — %.0fms since last dispatch (debounce)",A.name,B,(D-F)*1000);return
		G=A._confirm_handles.pop(B,_A)
		if G is not _A:G.cancel()
		E=A._ramp_tasks.pop(B,_A)
		if E is not _A and not E.done():E.cancel()
		H=A._last_press_times.get(B,0);A._last_press_times[B]=D;A._press_times[B]=D;A._held[B]=_C;I=C.get(_h,{});J=I.get(_f,{})
		if D-H<A._DOUBLE_TAP_WINDOW and J.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE:_LOGGER.info("'%s': button %d DOUBLE TAP (%.3fs since last press)",A.name,B,D-H);L=A._merge_v2_block(C,J);A.hass.async_create_task(A._dispatch(B,L));return
		K=C.get(CONF_ACTION_TYPE);M=I.get(_g,{});N=M.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE and not C.get(_Q,_C);O=K in A._HOLD_ACTIONS or C.get(_Q,_C)or N
		if not O:A._last_dispatch_times[B]=D;A.hass.async_create_task(A._dispatch(B,C))
		else:P=A._HOLD_CONFIRM_CYCLE if K==ACTION_ENTITY_TOGGLE and C.get(_Q,_C)else A._HOLD_CONFIRM;Q=A.hass.loop.call_later(P,A._on_hold_event,B);A._confirm_handles[B]=Q
	@callback
	def _handle_release(self,btn_num):
		B=btn_num;A=self;D=asyncio.get_event_loop().time();E=D-A._press_times.get(B,D);_LOGGER.debug("'%s': button %d release elapsed=%.3fs held=%s confirm=%s",A.name,B,E,A._held.get(B),B in A._confirm_handles)
		if A._held.get(B,_C):
			F=A._ramp_tasks.pop(B,_A)
			if F is not _A and not F.done():F.cancel()
			A._held.pop(B,_A);A._ramp_end_times[B]=D;H=E-A._HOLD_CONFIRM
			if H<A._RAMP_INTERVAL:
				C=A._buttons.get(B)
				if C is not _A:
					I=C.get(CONF_ACTION_TYPE)
					if I in(ACTION_RAISE,ACTION_LOWER):_LOGGER.debug("'%s': button %d short hold (%.0fms in ramp) — dispatching single step",A.name,B,H*1000);A.hass.async_create_task(A._dispatch(B,C))
			return
		G=A._confirm_handles.pop(B,_A)
		if G is not _A:G.cancel()
		C=A._buttons.get(B)
		if C is not _A and G is not _A:_LOGGER.info("'%s': button %d TAP (elapsed=%.3fs)",A.name,B,E);A._last_dispatch_times[B]=D;A.hass.async_create_task(A._dispatch(B,C))
	@callback
	def _on_hold_event(self,btn_num):
		B=btn_num;A=self;A._confirm_handles.pop(B,_A);C=A._buttons.get(B)
		if C is _A:return
		F=C.get(CONF_ACTION_TYPE);G=C.get(_Q,_C);_LOGGER.debug("'%s': button %d hold event — action=%s cycle_dim=%s led_mode=%s (hold-to-dim is driven by cycle_dim, NOT led_mode)",A.name,B,F,G,C.get(CONF_LED_MODE));I=C.get(_h,{});H=I.get(_g,{})
		if not G and H.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE:_LOGGER.info("'%s': button %d HOLD — dispatching custom hold action '%s'",A.name,B,H.get(CONF_ACTION_TYPE));A._held[B]=_B;J=A._merge_v2_block(C,H);A.hass.async_create_task(A._dispatch(B,J));return
		if F==ACTION_RAISE:E=_p;D=A._get_last_ramp_lights()
		elif F==ACTION_LOWER:E=_d;D=A._get_last_ramp_lights()
		elif F==ACTION_LIGHT_CYCLE_DIM or G:D=A._get_btn_light_entities(C);E=A._next_ramp_dir(B,D);_LOGGER.info("'%s': button %d HOLD — cycle_dim ramp %s on %s",A.name,B,E,D)
		else:_LOGGER.debug("'%s': button %d hold with 'Hold to dim' off — dispatching, no dim",A.name,B);A._held[B]=_B;A.hass.async_create_task(A._dispatch(B,C));return
		if not D:_LOGGER.debug("'%s': button %d hold event — no rampable lights, dispatching",A.name,B);A._held[B]=_B;A.hass.async_create_task(A._dispatch(B,C));return
		_LOGGER.info("'%s': button %d HOLD EVENT — ramp %s on %s",A.name,B,E,D);A._held[B]=_B;K=A.hass.async_create_task(A._ramp_loop(B,D,E));A._ramp_tasks[B]=K
	async def _ramp_loop(A,btn_num,entities,direction):
		C=direction
		try:
			while _B:
				D=_B
				for B in entities:
					E=A.hass.states.get(B)
					if E is _A:continue
					if E.state==_n:
						if C==_p:await A.hass.services.async_call(_I,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_e:1},blocking=_C);D=_C
						continue
					F=round((E.attributes.get(_H,0)or 0)/255*100);G=min(100,F+A._RAMP_STEP_PCT)if C==_p else max(0,F-A._RAMP_STEP_PCT)
					if G==F:continue
					D=_C
					if C==_d and G<=0:await A.hass.services.async_call(_I,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_C)
					else:await A.hass.services.async_call(_I,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_e:G,_A4:A._RAMP_INTERVAL},blocking=_C)
				if D:break
				await asyncio.sleep(A._RAMP_INTERVAL)
		except asyncio.CancelledError:pass
		finally:A._ramp_tasks.pop(btn_num,_A)
	_RAMP_DIR_RESET_WINDOW=5.
	def _next_ramp_dir(A,btn_num,entities=_A):
		D=entities;C=btn_num;F=asyncio.get_event_loop().time();E=A._ramp_end_times.get(C)
		if E is _A or F-E>A._RAMP_DIR_RESET_WINDOW:
			if D and all(A._light_at_max(B)for B in D):B=_d
			else:B=_p
		else:G=A._ramp_dirs.get(C,_d);B=_p if G==_d else _d
		A._ramp_dirs[C]=B;return B
	def _light_at_max(B,eid):
		A=B.hass.states.get(eid)
		if A is _A or A.state!='on':return _C
		return round((A.attributes.get(_H,0)or 0)/255*100)>=99
	def _is_btn_led_on(A,btn_num):
		B=btn_num;C=A._button_switches.get(B)
		if C is not _A:return bool(C.is_on)
		D=A._get_led_entity(B)
		if D:E=A.hass.states.get(D);return E is not _A and E.state=='on'
		return _C
	def _merge_v2_block(D,btn_cfg,block):
		A=block;B=dict(btn_cfg);B[CONF_ACTION_TYPE]=A.get(CONF_ACTION_TYPE,ACTION_NONE);C=A.get(CONF_ACTION_TARGET,'');B[CONF_ACTION_TARGET]=_normalize_action_target(C,B[CONF_ACTION_TYPE]);B[CONF_ENTITY_SETTINGS]=A.get(CONF_ENTITY_SETTINGS,{})
		if A.get(CONF_TARGET_BRIGHTNESS):B[CONF_TARGET_BRIGHTNESS]=int(A[CONF_TARGET_BRIGHTNESS])
		if A.get(CONF_TARGET_COLOR_TEMP):B[CONF_TARGET_COLOR_TEMP]=int(A[CONF_TARGET_COLOR_TEMP])
		if A.get(_M):B[_M]=A[_M]
		return B
	def _get_btn_light_entities(E,btn_cfg):
		A=btn_cfg;B=A.get(CONF_ACTION_TYPE)
		if B in(ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION,ACTION_LIGHT_CYCLE_DIM):return[A for A in _normalize_targets(A.get(CONF_ACTION_TARGET,[]))if A.startswith(_N)]
		if B==ACTION_STATEFUL_SCENE:
			C=A.get(CONF_ACTION_TARGET,'');D=E.hass.states.get(C)if C else _A
			if D:return[A for A in D.attributes.get(_AN,[])if A.startswith(_N)]
		if A.get(_Q,_C):return[A for A in _normalize_targets(A.get(CONF_ACTION_TARGET,[]))if A.startswith(_N)]
		return[]
	def _scene_light_entities(B,scene_id):
		A=B.hass.states.get(scene_id)
		if A is _A:return[]
		return[A for A in A.attributes.get(_AN,[])if A.startswith(_N)]
	def _get_last_ramp_lights(A):
		if A._last_action is _A:return[]
		B=A._last_action.get(_J,[])
		if B:return[A for A in B if A.startswith(_N)]
		D=A._last_action.get(_D)
		if D in(ACTION_STATEFUL_SCENE,ACTION_HA_SCENE):C=A._last_action.get(_A5,'');return A._scene_light_entities(C)if C else[]
		return[]
	async def _dispatch(A,btn_num,btn_cfg):
		X='delay';W='fade';G=btn_cfg;C=btn_num;F=G[CONF_ACTION_TYPE];I=G.get(CONF_ACTION_TARGET);S=G.get(CONF_ACTION_PARAMS,{})
		if F==ACTION_NONE:return
		elif F==ACTION_HA_SCENE:await A._activate_scene(I);await A._write_led_entity(C,_B);A._last_action={_D:ACTION_HA_SCENE,_A5:I}
		elif F==ACTION_STATEFUL_SCENE:await A._activate_stateful_scene(C,G,I)
		elif F==ACTION_AUTOMATION:await A._trigger_automation(I);await A._write_led_entity(C,_B)
		elif F==ACTION_SCRIPT:await A._run_script(I,S);await A._write_led_entity(C,_B)
		elif F==ACTION_ENTITY_TOGGLE:
			D=_normalize_targets(I);O=int(G.get(CONF_TARGET_BRIGHTNESS)or 0);P=int(G.get(CONF_TARGET_COLOR_TEMP)or 0);J=G.get(CONF_ENTITY_SETTINGS,{});Z=G.get(CONF_LED_MODE,LED_MODE_ROOM);a=G.get(_h,{});b=a.get(_A7,{});U=b.get('entity_settings',{})
			if Z==LED_MODE_SCENE:
				if A._is_btn_led_on(C):
					_LOGGER.info("'%s': button %d PRESS OFF (scene mode) — LED was ON, applying off_level to %s",A.name,C,D)
					for B in D:
						H=B.split(_Y)[0];V=U.get(B,{});K=int(V.get(_H)or 0)
						if H==_I and K>0:_LOGGER.info("'%s': button %d  → %s dim to %d%%",A.name,C,B,K);await A.hass.services.async_call(_I,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_e:K},blocking=_B)
						else:_LOGGER.info("'%s': button %d  → %s turn OFF",A.name,C,B);await A.hass.services.async_call(H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_J:D};await A._write_led_entity(C,_C)
				else:
					_LOGGER.info("'%s': button %d PRESS ON (scene mode) — LED was OFF, activating scene on %s",A.name,C,D)
					for B in D:
						if B.startswith(_N):E=J.get(B,{});L=int(E.get(_H)or O);M=int(E.get(_c)or P);Q=E.get(_q);N=float(E.get(W)or 0);R=float(E.get(X)or 0);_LOGGER.info("'%s': button %d  → %s bri=%d%% cct=%dK fade=%.1fs",A.name,C,B,L,M,N);await A._apply_light_settings(B,L,M,Q,N,R)
						else:H=B.split(_Y)[0];await A.hass.services.async_call(H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_J:D}
			else:
				T=_C
				if D:Y=A.hass.states.get(D[0]);T=Y is not _A and Y.state not in(_n,_o,_A3,_W,_k)
				c=any(int(J.get(A,{}).get(_H)or O)>0 or int(J.get(A,{}).get(_c)or P)>0 or bool(J.get(A,{}).get(_q))for A in D if A.startswith(_N))if D else _C
				if not T and c:
					for B in D:
						if B.startswith(_N):E=J.get(B,{});L=int(E.get(_H)or O);M=int(E.get(_c)or P);Q=E.get(_q);N=float(E.get(W)or 0);R=float(E.get(X)or 0);await A._apply_light_settings(B,L,M,Q,N,R)
						else:H=B.split(_Y)[0];await A.hass.services.async_call(H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_J:D};await A._write_led_entity(C,_B)
				elif T and U:
					for B in D:
						H=B.split(_Y)[0];V=U.get(B,{});K=int(V.get(_H)or 0)
						if H==_I and K>0:await A.hass.services.async_call(_I,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_e:K},blocking=_B)
						else:await A.hass.services.async_call(H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_J:D};await A._write_led_entity(C,_C)
				else:await A._entity_toggle(I);await A._write_led_entity(C,not T)
		elif F==ACTION_SINGLE_ACTION:
			D=_normalize_targets(I);O=int(G.get(CONF_TARGET_BRIGHTNESS)or 0);P=int(G.get(CONF_TARGET_COLOR_TEMP)or 0);J=G.get(CONF_ENTITY_SETTINGS,{});_LOGGER.info("'%s': button %d SINGLE ACTION — activating %s",A.name,C,D)
			for B in D:
				if B.startswith(_N):E=J.get(B,{});L=int(E.get(_H)or O);M=int(E.get(_c)or P);Q=E.get(_q);N=float(E.get(W)or 0);R=float(E.get(X)or 0);await A._apply_light_settings(B,L,M,Q,N,R)
				else:H=B.split(_Y)[0];await A.hass.services.async_call(H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B},blocking=_B)
			A._last_action={_D:ACTION_SINGLE_ACTION,_J:D}
		elif F==ACTION_COVER_CYCLE:await A._cover_cycle(C,I)
		elif F==ACTION_LIGHT_CYCLE_DIM:d=S.get('levels',DIM_CYCLE_LEVELS);await A._light_cycle_dim(C,I,d)
		elif F==ACTION_RAISE:await A._raise(S)
		elif F==ACTION_LOWER:await A._lower(S)
		else:_LOGGER.error("'%s': unknown action_type '%s'",A.name,F);return
		if A._last_action is not _A and F not in(ACTION_RAISE,ACTION_LOWER):A._last_action[_j]=C
		A._notify_state_sensors()
	async def _apply_light_settings(E,eid,bri,cct,hs_color=_A,fade=0,delay=0):
		H=delay;G=hs_color;F=eid;D=cct;C=bri;A=fade
		if H>0:await asyncio.sleep(H)
		if C>0 and D>0:
			I={ATTR_ENTITY_ID:F,_AI:D}
			if A>0:I[_A4]=A
			await E.hass.services.async_call(_I,SERVICE_TURN_ON,I,blocking=_B);J={ATTR_ENTITY_ID:F,_e:C}
			if A>0:J[_A4]=A
			await E.hass.services.async_call(_I,SERVICE_TURN_ON,J,blocking=_B)
		else:
			B={ATTR_ENTITY_ID:F}
			if C>0:B[_e]=C
			if D>0:B[_AI]=D
			if G:B[_q]=G
			if A>0:B[_A4]=A
			await E.hass.services.async_call(_I,SERVICE_TURN_ON,B,blocking=_B)
	async def _activate_scene(B,scene_id):A=scene_id;await B.hass.services.async_call('scene','turn_on',{ATTR_ENTITY_ID:A},blocking=_B);_LOGGER.debug('Scene activated: %s',A)
	async def _activate_stateful_scene(A,btn_num,btn_cfg,scene_id):
		D=btn_cfg;C=scene_id;B=btn_num;await A._activate_scene(C);A._active_scene_btn=B;E=D.get(_M)or A.scene_group
		if E:_SCENE_GROUPS[E]=B
		await A._sync_leds(B);await A._write_group_leds(B,D);A._last_action={_D:ACTION_STATEFUL_SCENE,_A5:C,_j:B};_LOGGER.debug("Stateful scene '%s' activated on btn %d",C,B)
	async def _trigger_automation(A,automation_id):B=automation_id;await A.hass.services.async_call('automation','trigger',{ATTR_ENTITY_ID:B,'skip_condition':_B},blocking=_B);A._last_action={_D:ACTION_AUTOMATION,_E:B}
	async def _run_script(B,script_id,params):
		D=params;C=script_id;A='variables';E={ATTR_ENTITY_ID:C}
		if A in D:E[A]=D[A]
		await B.hass.services.async_call('script','turn_on',E,blocking=_C);B._last_action={_D:ACTION_SCRIPT,_E:C}
	async def _entity_toggle(A,targets):
		B=_normalize_targets(targets)
		for C in B:D=C.split(_Y)[0];await A.hass.services.async_call(D,SERVICE_TOGGLE,{ATTR_ENTITY_ID:C},blocking=_B)
		A._last_action={_D:ACTION_ENTITY_TOGGLE,_J:B}
	_COVER_CYCLE_WINDOW=6e1
	async def _cover_cycle(B,btn_num,targets):
		T='moving';P='close';O='phase';N='ts';G=btn_num;F='open';E='dir';C=_normalize_targets(targets)
		if not C:return
		H=B.hass.states.get(C[0]);L=H.state if H is not _A else _A;I=H.attributes.get(_AL)if H is not _A else _A;M=asyncio.get_event_loop().time();A=B._cover_cycle_mem.get(G);J=M-A.get(N,0)if A else 1e9;U=A is not _A and J<=B._COVER_CYCLE_WINDOW;V=_cover_travel_time(B.hass,C[0]);Q=bool(A and A.get(O)==T and J<V)
		if Q:K=_AK;B._cover_cycle_mem[G]={O:'idle',E:A[E],N:M}
		else:
			if I is not _A:R=I<=0;S=I>=100
			else:R=L==_o;S=L==F
			if R:D=F
			elif S:D=P
			elif U and A and A.get(E):D=P if A[E]==F else F
			else:D=P
			K=_AG if D==F else _A0;B._cover_cycle_mem[G]={O:T,E:D,N:M}
		await B.hass.services.async_call(_z,K,{ATTR_ENTITY_ID:C},blocking=_B);B._last_action={_D:ACTION_COVER_CYCLE,_J:C,'state':K};_LOGGER.debug("'%s': button %d cover cycle — state=%s pos=%s since=%.1fs prev=%s moving=%s → %s",B.name,G,L,I,J if J<1e8 else-1,A,Q,K)
	async def _light_cycle_dim(A,btn_num,targets,levels):
		E=btn_num;D=levels;B=_normalize_targets(targets);C=A._light_dim_indices.get(E,len(D))
		if C>=len(D):C=0
		else:C+=1
		if C>=len(D):await A.hass.services.async_call(_I,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_B);A._light_dim_indices[E]=len(D);A._last_action={_D:ACTION_LIGHT_CYCLE_DIM,_J:B,_H:0};_LOGGER.debug('Light cycle: turned off %s',B)
		else:F=D[C];G=int(F/100*255);await A.hass.services.async_call(_I,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_H:G},blocking=_B);A._light_dim_indices[E]=C;A._last_action={_D:ACTION_LIGHT_CYCLE_DIM,_J:B,_H:F};_LOGGER.debug('Light cycle: %s → %d%%',B,F)
	def _last_action_light_entities(A):
		if A._last_action is _A:return[]
		B=A._last_action.get(_J,[])
		if B:return[A for A in B if A.startswith(_N)]
		D=A._last_action.get(_D)
		if D in(ACTION_STATEFUL_SCENE,ACTION_HA_SCENE):C=A._last_action.get(_A5,'');return A._scene_light_entities(C)if C else[]
		return[]
	async def _raise(A,params):
		if A._last_action is _A:_LOGGER.debug("'%s': RAISE pressed but no prior context",A.name);return
		D=A._last_action;F=D.get(_D);B=D.get(_J,[])
		if F==ACTION_COVER_CYCLE or _entities_are_covers(B):
			await A.hass.services.async_call(_z,_AG,{ATTR_ENTITY_ID:B},blocking=_B)
			for(G,C)in A._buttons.items():
				if C.get(CONF_ACTION_TYPE)==ACTION_COVER_CYCLE and C.get(CONF_ACTION_TARGET):
					H=_normalize_targets(C[CONF_ACTION_TARGET])
					if any(A in B for A in H):A._cover_states[G]=COVER_STATE_OPEN
		else:
			E=A._last_action_light_entities()
			if E:await A._adjust_light_brightness(E,+RAISE_LOWER_STEP)
			else:_LOGGER.debug("'%s': RAISE — no applicable entities from last action",A.name)
	async def _lower(A,params):
		if A._last_action is _A:_LOGGER.debug("'%s': LOWER pressed but no prior context",A.name);return
		D=A._last_action;F=D.get(_D);B=D.get(_J,[])
		if F==ACTION_COVER_CYCLE or _entities_are_covers(B):
			await A.hass.services.async_call(_z,_A0,{ATTR_ENTITY_ID:B},blocking=_B)
			for(G,C)in A._buttons.items():
				if C.get(CONF_ACTION_TYPE)==ACTION_COVER_CYCLE and C.get(CONF_ACTION_TARGET):
					H=_normalize_targets(C[CONF_ACTION_TARGET])
					if any(A in B for A in H):A._cover_states[G]=COVER_STATE_CLOSE
		else:
			E=A._last_action_light_entities()
			if E:await A._adjust_light_brightness(E,-RAISE_LOWER_STEP)
			else:_LOGGER.debug("'%s': LOWER — no applicable entities from last action",A.name)
	async def _adjust_light_brightness(B,entities,delta_pct):
		for A in entities:
			C=B.hass.states.get(A)
			if C is _A:continue
			G=A.split(_Y)[0]
			if G!=_I:continue
			H=C.attributes.get(_H,0)or 0;D=round(H/255*100);E=max(0,min(100,D+delta_pct));F=int(E/100*255)
			if F<=0:await B.hass.services.async_call(_I,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:A},blocking=_B)
			else:await B.hass.services.async_call(_I,SERVICE_TURN_ON,{ATTR_ENTITY_ID:A,_H:F},blocking=_B)
			_LOGGER.debug('Brightness adjust %s: %d%% → %d%%',A,D,E)
def _normalize_targets(targets):
	A=targets
	if A is _A:return[]
	if isinstance(A,str):
		if not A:return[]
		if','in A:return[A.strip()for A in A.split(',')if A.strip()]
		return[A]
	if isinstance(A,(list,tuple)):return[str(A)for A in A if A]
	return[str(A)]
def _entities_are_covers(entities):return any(A.startswith('cover.')for A in entities)