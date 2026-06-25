from __future__ import annotations
_AC='close_cover'
_AB='open_cover'
_AA='entity_id'
_A9='keypad_type'
_A8='lutron_type'
_A7='cover'
_A6='color_temp_kelvin'
_A5='debug_leds'
_A4='_sidebar_show'
_A3='/lutron_keypad_panel.js'
_A2='area_name'
_A1='not_found'
_A0='button'
_z='button_names'
_y='lower_button'
_x='raise_button'
_w='configurable_buttons'
_v='double_tap'
_u='off_level'
_t='generic'
_s='scene_id'
_r='transition'
_q='unavailable'
_p='closed'
_o='controllers'
_n='success'
_m='_controller'
_l='entry_controllers'
_k='leap_button_map'
_j='_v2_blocks'
_i='hold'
_h='hs_color'
_g='up'
_f='off'
_e='jti'
_d='unknown'
_c='none'
_b='leap_button_number'
_a='button_number'
_Z='buttons'
_Y='model'
_X='model_number'
_W='button_numbers'
_V='brightness_pct'
_U='down'
_T='color_temp'
_S='.'
_R='lutron_caseta'
_Q='cycle_dim'
_P='license_key'
_O='switch'
_N='light.'
_M='entry_id'
_L='scene_group'
_K='name'
_J='serial'
_I='entities'
_H='light'
_G='brightness'
_F='id'
_E='device_id'
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
KEYPAD_SCHEMA=vol.Schema({vol.Required(_K):cv.string,vol.Optional(CONF_DEVICE_SERIAL,default=''):cv.string,vol.Optional(CONF_DEVICE_NAME,default=''):cv.string,vol.Optional(CONF_AREA_NAME,default=''):cv.string,vol.Optional(CONF_KEYPAD_TYPE,default=_t):cv.string,vol.Optional(_L,default=''):cv.string,vol.Required(CONF_BUTTONS):vol.All(cv.ensure_list,[BUTTON_SCHEMA])})
CONFIG_SCHEMA=vol.Schema({DOMAIN:vol.Schema({vol.Required('keypads'):vol.All(cv.ensure_list,[KEYPAD_SCHEMA])})},extra=vol.ALLOW_EXTRA)
PLATFORMS=['sensor',_O,'select','text']
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
		if C.get(_L):B[_L]=C[_L]
		if A.get(CONF_LED_MODE):B[CONF_LED_MODE]=A[CONF_LED_MODE]
		if C.get(CONF_TARGET_BRIGHTNESS):B[CONF_TARGET_BRIGHTNESS]=int(C[CONF_TARGET_BRIGHTNESS])
		if C.get(CONF_TARGET_COLOR_TEMP):B[CONF_TARGET_COLOR_TEMP]=int(C[CONF_TARGET_COLOR_TEMP])
		if C.get(CONF_ENTITY_SETTINGS):B[CONF_ENTITY_SETTINGS]=C[CONF_ENTITY_SETTINGS]
		if A.get(_Q):B[_Q]=_B
		H=A.get(_u,{});I=A.get(_v,{});J=A.get(_i,{})
		if D is not _A or H or I or J:B[_j]={K:D or{},_u:H,_v:I,_i:J}
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
	K=hass;A=entry;R=bool(A.data.get(_W));e=_X in A.data
	if R and e:return
	B=str(A.data.get(CONF_DEVICE_SERIAL,'')).strip();G=str(A.data.get(_E,'')).strip();f=A.data.get(CONF_AREA_NAME,'');g=A.data.get(CONF_DEVICE_NAME,'')
	if not B:return
	from.const import KEYPAD_LAYOUTS as S,KEYPAD_GENERIC as T;from.config_flow import _infer_keypad_type as h;U=A.data.get(_A8,'');V=h(U)if U else A.data.get(CONF_KEYPAD_TYPE,T);l,W=S.get(V,S[T])
	if R:
		for L in _iter_lutron_bridges(K):
			try:O=L.get_devices()
			except Exception as P:_LOGGER.debug("get_devices() failed backfilling model for '%s': %s",A.title,P);continue
			for F in O.values():
				if B and str(F.get(_J,''))==B or G and str(F.get(_E,''))==G:I=F.get(_Y,'')or'';K.config_entries.async_update_entry(A,data={**A.data,_X:I});_LOGGER.debug("Backfilled model_number=%r for '%s'",I,A.title);return
		_LOGGER.debug("Could not backfill model_number for '%s' (serial=%s)",A.title,B);return
	def i(full_name,area,dev):
		C=full_name;A=C.strip()
		for B in[f"{area} {dev}",dev,area]:
			B=B.strip()
			if B and A.lower().startswith(B.lower()):A=A[len(B):].strip();break
		return A.title()if A else C.strip()
	for L in _iter_lutron_bridges(K):
		X=getattr(L,_Z,_A)or{}
		if not X:continue
		Y=[A for A in X.values()if B and str(A.get(_J,''))==B or G and str(A.get('parent_device',''))==G]
		if not Y:continue
		H=[];C=_A;D=_A;Z={};Q=[]
		for M in Y:
			a=M.get(_a)
			if a is _A:continue
			try:J=int(a)
			except(TypeError,ValueError):continue
			N=M.get('button_name')or M.get(_K,'');b=N.lower();j=M.get('button_led')is not _A
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
				if B and str(F.get(_J,''))==B or G and str(F.get(_E,''))==G:I=F.get(_Y,'')or'';break
		except Exception as P:_LOGGER.debug("get_devices() failed fetching model for '%s': %s",A.title,P)
		k={_W:H,_w:d,_x:C,_y:D,_z:Z,_k:{},CONF_KEYPAD_TYPE:V,_X:I};_LOGGER.info("Auto-detected layout for '%s' (serial=%s): %d buttons, configurable=%s raise=%s lower=%s",A.title,B,len(H),d,C,D);K.config_entries.async_update_entry(A,data={**A.data,**k});return
	_LOGGER.warning("Could not auto-detect button layout for '%s' (serial=%s) — bridge not found or carries no button data.",A.title,B)
async def _find_led_entities(hass,config_entry):
	B=config_entry;E=str(B.data.get(CONF_DEVICE_SERIAL,'')).strip();F=str(B.data.get(_E,'')).strip();_LOGGER.debug("LED discovery starting for '%s' — serial=%s device_id=%s",B.title,E,F);I=dr.async_get(hass);N=er.async_get(hass);_LOGGER.debug('LED discovery: %d devices in registry',len(I.devices));C=_A
	for D in I.devices.values():
		for(O,P,*Q)in D.identifiers:
			if O!=_R:continue
			K=str(P).strip()
			if E and K==E or F and K==F:C=D;break
		if C:break
	if C is _A:
		_LOGGER.warning('LED discovery: no lutron_caseta device matched serial=%s device_id=%s. Dumping all device identifiers:',E,F)
		for D in I.devices.values():_LOGGER.warning("  Device '%s': identifiers=%s",D.name,list(D.identifiers))
		return{}
	J=er.async_entries_for_device(N,C.id);_LOGGER.debug("LED discovery: found lutron device '%s' (id=%s) with %d entities: %s",C.name,C.id,len(J),[(A.entity_id,A.domain,A.unique_id)for A in J]);G={}
	for A in J:
		if A.domain!=_O:continue
		H=' '.join(filter(_A,[A.name,A.original_name,A.unique_id])).lower();_LOGGER.debug("LED discovery: switch entity %s — haystack='%s'",A.entity_id,H)
		if'led'not in H:continue
		L=_re.search('button[_\\s]+(\\d+)[_\\s]+led',H)
		if L:M=int(L.group(1));G[M]=A.entity_id;_LOGGER.debug('LED discovery: button %d → %s',M,A.entity_id)
		else:_LOGGER.warning("LED discovery: '%s' contains 'led' but button number regex did not match — haystack='%s'",A.entity_id,H)
	if G:_LOGGER.info("LED discovery for '%s': %s",B.title,G)
	else:_LOGGER.warning("LED discovery for '%s': no LED entities mapped (keypad_type=%s). If your keypad has LEDs, configure led_entity manually in the options flow, or check the debug_leds service output.",B.title,B.data.get(_A9))
	return G
def _extract_button_number(btn_entry,hass):
	C=btn_entry;B=C.unique_id or'';G=C.entity_id or'';A=_re.search('_(\\d+)$',B)
	if A:return int(A.group(1))
	A=_re.search('button[_\\s](\\d+)',B.lower())
	if A:return int(A.group(1))
	D=hass.states.get(G)
	if D:
		for H in(_a,_b,'button_index'):
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
	G=hass;D=config_entry;M=str(D.data.get(CONF_DEVICE_SERIAL,'')).strip();N=er.async_get(G);H=_find_lutron_device(G,D)
	if H is _A:return{}
	K=er.async_entries_for_device(N,H.id);I=[A for A in K if A.domain==_A0];F=[A for A in K if A.domain==_O and A.entity_id.endswith('_led')];_LOGGER.debug("LED discovery for '%s': device '%s' has %d button entities, %d LED switch entities",D.title,H.name,len(I),len(F))
	if not F:_LOGGER.debug("LED discovery: no switch.*_led entities on device '%s'",H.name);return{}
	O={A.entity_id for A in F};A={}
	for E in I:
		P=E.entity_id[len('button.'):];J=f"switch.{P}_led"
		if J not in O:continue
		B=_extract_button_number(E,G)
		if B is not _A:A[B]=J;_LOGGER.debug("LED (A): button %d → '%s'",B,J)
	if A:_LOGGER.info("LED discovery for '%s' (strategy A): %s",D.title,A);return A
	L={A.unique_id:A for A in I if A.unique_id}
	for C in F:
		if not C.unique_id:continue
		E=L.get(C.unique_id)
		if E is _A:Q=_re.sub('[_-]?led$','',C.unique_id).rstrip('_-');E=L.get(Q)
		if E:
			B=_extract_button_number(E,G)
			if B is not _A:A[B]=C.entity_id;_LOGGER.debug("LED (B): button %d → '%s'",B,C.entity_id)
	if A:_LOGGER.info("LED discovery for '%s' (strategy B): %s",D.title,A);return A
	for C in F:
		B=_extract_btn_num_from_led_uid(C.unique_id or'',M)
		if B is not _A:A[B]=C.entity_id;_LOGGER.debug("LED (C): button %d → '%s'",B,C.entity_id)
	if A:_LOGGER.info("LED discovery for '%s' (strategy C): %s",D.title,A);return A
	_LOGGER.warning("LED discovery for '%s': all strategies failed. button entities=%s  LED entities=%s  Configure led_entity manually in options or run debug_leds service.",D.title,[A.entity_id for A in I],[A.entity_id for A in F]);return A
async def _async_debug_leds(hass,call):
	C=hass;A=[];J=C.data.get(DOMAIN,{}).get(_l,{})
	if not J:A.append('No entry controllers found in hass.data — is the integration loaded?')
	for(R,B)in J.items():
		A.append(f"\n{"="*60}");A.append(f"Keypad : {B.name}");A.append(f"Serial : {B.serial}");A.append(f"device_id: {B.device_id}");A.append(f"LED map (auto-discovered): {B._led_map}");A.append(f"Button switches registered: {list(B._button_switches.keys())}")
		for(F,K)in B._buttons.items():
			O=K.get(CONF_ACTION_TYPE,_c);L=K.get(CONF_LED_ENTITY,'');M=B._led_map.get(F,'');G=L or M;A.append(f"\n  Button {F}  action={O}");A.append(f"    manual led_entity : '{L}'");A.append(f"    auto-discovered   : '{M}'");A.append(f"    resolved LED      : '{G}'")
			if G:D=C.states.get(G);A.append(f"    LED entity state  : {D.state if D else"⚠ ENTITY NOT FOUND"}")
			else:A.append('    ⚠ NO LED ENTITY — auto-discovery failed and no manual led_entity set')
			H=B._button_switches.get(F);A.append(f"    HA switch state   : {"ON"if H and H.is_on else"OFF"}{""if H else"  ⚠ switch entity not registered"}")
	A.append(f"\n{"="*60}");A.append("All switch entities with 'led' in entity_id:")
	for D in C.states.async_all(_O):
		if'led'in D.entity_id.lower():A.append(f"  {D.entity_id}: {D.state}")
	A.append("\nDevice registry — devices with 'lutron' identifiers:");P=dr.async_get(C)
	for I in P.devices.values():
		if any('lutron'in str(A).lower()for A in I.identifiers):A.append(f"  '{I.name}'  identifiers={list(I.identifiers)}")
	A.append('\nEntity registry — lutron_caseta switch entities:');Q=er.async_get(C)
	for E in Q.entities.values():
		if E.domain==_O and E.platform==_R:A.append(f"  {E.entity_id}  unique_id={E.unique_id}  device_id={E.device_id}")
	N='\n'.join(A);_LOGGER.warning('LED DEBUG REPORT:\n%s',N);C.bus.async_fire('lutron_keypad_controller_debug',{'report':N})
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/get_entries"})
@websocket_api.async_response
async def _ws_get_entries(hass,connection,msg):
	B=[]
	for A in hass.config_entries.async_entries(DOMAIN):
		if A.data.get(_m):continue
		B.append({_M:A.entry_id,'title':A.title,'data':dict(A.data),'options':dict(A.options),'state':A.state.value})
	connection.send_result(msg[_F],B)
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/save_keypad_config",vol.Required(_M):str,vol.Required(_Z):dict})
@websocket_api.async_response
async def _ws_save_keypad_config(hass,connection,msg):
	E=connection;B=msg;A=hass;D=B[_M];F=B[_Z];C=A.config_entries.async_get_entry(D)
	if C is _A or C.domain!=DOMAIN:E.send_error(B[_F],_A1,f"Entry '{D}' not found");return
	A.config_entries.async_update_entry(C,options={**C.options,_Z:F});A.async_create_task(A.config_entries.async_reload(D));E.send_result(B[_F],{_n:_B})
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/discover_keypads"})
@websocket_api.async_response
async def _ws_discover_keypads(hass,connection,msg):
	from.config_flow import _infer_keypad_type as E,LUTRON_TYPE_MAP as F;G={str(A.data.get(CONF_DEVICE_SERIAL,''))for A in hass.config_entries.async_entries(DOMAIN)};D=[]
	for H in _iter_lutron_bridges(hass):
		try:I=H.get_devices()
		except Exception as J:_LOGGER.debug('get_devices() failed during discovery: %s',J);continue
		for A in I.values():
			B=str(A.get(_J,''))
			if not B or B in G:continue
			C=A.get(_D,'')
			if C not in F:continue
			D.append({_J:B,_K:A.get(_K,''),'area':A.get(_A2,''),_D:C,_A9:E(C),_Y:A.get(_Y,'')or'',_E:str(A.get(_E,''))})
	connection.send_result(msg[_F],D)
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/add_keypad",vol.Required(_J):str,vol.Required(_K):str,vol.Optional(_E,default=''):str})
@websocket_api.async_response
async def _ws_add_keypad(hass,connection,msg):
	H=connection;G=hass;A=msg;from.config_flow import _infer_keypad_type as O,_detect_button_layout as P;C=A[_J];Q=(A.get(_K)or C).strip();D=A.get(_E,'');E=I=J=K=''
	for R in _iter_lutron_bridges(G):
		try:S=R.get_devices()
		except Exception:continue
		for B in S.values():
			if str(B.get(_J,''))==C:E=B.get(_D,'');I=B.get(_A2,'');J=B.get(_K,'');K=B.get(_Y,'')or'';D=str(B.get(_E,''))or D;break
		if E:break
	L=O(E);T=P(G,C,L,device_name=J,area_name=I,device_id=D);U={_K:Q,CONF_DEVICE_SERIAL:C,CONF_DEVICE_NAME:J,CONF_AREA_NAME:I,CONF_KEYPAD_TYPE:L,_A8:E,_X:K,_E:D,**T};F=await G.config_entries.flow.async_init(DOMAIN,context={'source':'panel'},data=U)
	if F.get(_D)=='create_entry':M=F.get('result');H.send_result(A[_F],{_n:_B,_M:M.entry_id if M else''})
	elif F.get(_D)=='abort':N=F.get('reason',_d);H.send_error(A[_F],N,f"Could not add keypad: {N}")
	else:H.send_error(A[_F],'flow_error','Unexpected flow result')
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/delete_keypad",vol.Required(_M):str})
@websocket_api.async_response
async def _ws_delete_keypad(hass,connection,msg):
	C=connection;A=msg;B=A[_M];D=hass.config_entries.async_get_entry(B)
	if D is _A or D.domain!=DOMAIN:C.send_error(A[_F],_A1,f"Entry '{B}' not found");return
	await hass.config_entries.async_remove(B);C.send_result(A[_F],{_n:_B})
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/license_status",vol.Optional(_M):str})
@websocket_api.async_response
async def _ws_license_status(hass,connection,msg):
	N='error';M='valid';L='has_key';H='loaded';F=connection;E=msg;C=hass;from.license import LicenseError as O,load_license_cache as P,validate_license_offline as Q;I=E.get(_M)
	if I:D=C.config_entries.async_get_entry(I)
	else:J=C.config_entries.async_entries(DOMAIN);D=J[0]if J else _A
	R=await async_get_instance_id(C);A={'instance_id':R,L:_C,M:_C,H:_C,N:_A}
	if D is _A:F.send_result(E[_F],A);return
	A[_M]=D.entry_id;A[H]=D.state.value==H;G=(D.options.get(_P)or'').strip();A[L]=bool(G)
	if not G:F.send_result(E[_F],A);return
	S=await async_get_integration(C,DOMAIN)
	try:B=Q(G,current_version=str(S.version));A.update({M:_B,_e:B.jti,'product':B.product,'expires_at':B.expires_at,'binding':B.binding,'bound_instance':B.instance_id,'max_version':B.max_version,'warn_only':B.warn_only})
	except O as T:A[N]=str(T)
	K=await P(C)
	if A.get(_e)and K.get(_e)==A.get(_e):A['last_check']=K.get('last_ok')
	F.send_result(E[_F],A)
@websocket_api.websocket_command({vol.Required(_D):f"{DOMAIN}/set_license",vol.Required(_M):str,vol.Required(_P):str})
@websocket_api.async_response
async def _ws_set_license(hass,connection,msg):
	D=connection;B=msg;A=hass;C=A.config_entries.async_get_entry(B[_M])
	if C is _A or C.domain!=DOMAIN:D.send_error(B[_F],_A1,'Entry not found');return
	E={**C.options,_P:B[_P].strip()};A.config_entries.async_update_entry(C,options=E)
	for F in A.config_entries.async_entries(DOMAIN):A.async_create_task(A.config_entries.async_reload(F.entry_id))
	D.send_result(B[_F],{_n:_B})
async def _register_panel_once(hass):
	C='_panel_registered';A=hass
	if A.data.get(DOMAIN,{}).get(C):return
	B=_COMPONENT_DIR/'frontend'/'lutron_panel.js'
	try:from homeassistant.components.http import StaticPathConfig as D;await A.http.async_register_static_paths([D(_A3,str(B),cache_headers=_C)])
	except(AttributeError,ImportError):
		try:A.http.register_static_path(_A3,str(B),cache_headers=_C)
		except Exception as E:_LOGGER.warning('Could not register static path for panel: %s',E)
	websocket_api.async_register_command(A,_ws_get_entries);websocket_api.async_register_command(A,_ws_save_keypad_config);websocket_api.async_register_command(A,_ws_discover_keypads);websocket_api.async_register_command(A,_ws_add_keypad);websocket_api.async_register_command(A,_ws_delete_keypad);websocket_api.async_register_command(A,_ws_license_status);websocket_api.async_register_command(A,_ws_set_license);A.data.setdefault(DOMAIN,{})[C]=_B;A.data[DOMAIN][_A4]=await _load_sidebar_show(A);_update_sidebar_panel(A)
@callback
def async_set_sidebar(hass,show):hass.data.setdefault(DOMAIN,{})[_A4]=bool(show);_update_sidebar_panel(hass)
@callback
def _update_sidebar_panel(hass):
	F='lutron-keypads';E='_sidebar_shown';D='_panel_registered_url';C=hass;A=C.data.setdefault(DOMAIN,{});B=bool(A.get(_A4))
	if A.get(D)and A.get(E)==B:return
	if A.get(D):
		try:frontend.async_remove_panel(C,F)
		except Exception:pass
	try:frontend.async_register_built_in_panel(C,component_name='custom',sidebar_title='Lutron Keypads'if B else _A,sidebar_icon='mdi:keyboard-outline'if B else _A,frontend_url_path=F,config={'_panel_custom':{_K:'lutron-keypad-panel','module_url':_A3}},require_admin=_B);A[D]=_B;A[E]=B
	except Exception as G:_LOGGER.warning('Could not register Lutron Keypads panel: %s',G)
_SIDEBAR_STORE_KEY='lutron_keypad_controller_sidebar'
async def _load_sidebar_show(hass):from homeassistant.helpers.storage import Store;A=Store(hass,1,_SIDEBAR_STORE_KEY);B=await A.async_load()or{};return bool(B.get('show',_C))
async def _save_sidebar_show(hass,show):from homeassistant.helpers.storage import Store;A=Store(hass,1,_SIDEBAR_STORE_KEY);await A.async_save({'show':bool(show)})
@callback
def _async_ensure_controller_entry(hass):
	A=hass
	if any(A.data.get(_m)for A in A.config_entries.async_entries(DOMAIN)):return
	A.async_create_task(A.config_entries.flow.async_init(DOMAIN,context={'source':'controller'},data={}))
async def _async_setup_controller_entry(hass,entry):await _register_panel_once(hass);await hass.config_entries.async_forward_entry_setups(entry,[_O]);return _B
async def async_setup(hass,config):
	B=config;A=hass;A.data.setdefault(DOMAIN,{});await _register_panel_once(A)
	if DOMAIN not in B:return _B
	E=B[DOMAIN].get('keypads',[]);C=[]
	for F in E:D=LutronKeypadsController(A,F);C.append(D);D.async_register()
	A.data[DOMAIN][_o]=C;A.services.async_register(DOMAIN,_A5,_async_debug_leds);return _B
async def async_setup_entry(hass,entry):
	B=hass;A=entry;B.data.setdefault(DOMAIN,{})
	if A.data.get(_m):return await _async_setup_controller_entry(B,A)
	H=B.data[DOMAIN].setdefault('_reload_listeners',set())
	if A.entry_id not in H:A.add_update_listener(_async_reload_entry);H.add(A.entry_id)
	await _register_panel_once(B);_async_ensure_controller_entry(B);D=(A.options.get(_P)or'').strip()
	if not D:
		for O in B.config_entries.async_entries(DOMAIN):
			I=(O.options.get(_P)or'').strip()
			if I:D=I;break
	if not D:D=await recall_license_key(B)
	if not D:_LOGGER.error("Ctrlable Lutron Keypad: no license key configured. Open the integration's Configure dialog and paste your license key (obtain one from portal.ctrlable.com).");return _C
	if not(A.options.get(_P)or'').strip():B.config_entries.async_update_entry(A,options={**A.options,_P:D})
	P=await async_get_integration(B,DOMAIN);Q=str(P.version)
	try:C=validate_license_offline(D,current_version=Q)
	except LicenseError as R:_LOGGER.error('Ctrlable Lutron Keypad: license validation failed — %s',R);return _C
	if C.warn_only:_LOGGER.warning('Ctrlable Lutron Keypad: license has expired but warn_only mode is active. Please renew your license.')
	E=await async_get_instance_id(B)
	if C.binding=='instance'and C.instance_id and C.instance_id!=E:_LOGGER.error('Ctrlable Lutron Keypad: license is bound to instance %s; this HA is %s.',C.instance_id,E);return _C
	J=await check_revocation_online(C.jti,instance_id=E)
	if J is _C:_LOGGER.error('Ctrlable Lutron Keypad: license rejected by portal. Aborting setup.');return _C
	K=await load_license_cache(B);L=K.get('last_ok')if K.get(_e)==C.jti else _A
	if J is _B:await save_license_cache(B,C.jti)
	elif L is not _A:
		M=(time.time()-L)/86400
		if M>30:_LOGGER.warning('Ctrlable Lutron Keypad: portal unreachable for %.0f days. Ensure this device can reach portal.ctrlable.com periodically.',M)
	await remember_license_key(B,D);B.data.setdefault(DOMAIN,{});B.data[DOMAIN].setdefault(_o,[]);B.data[DOMAIN].setdefault(_l,{});await _auto_refresh_button_layout(B,A)
	if not A.data.get(_W)or _X not in A.data:
		async def N(_event=_A):await _auto_refresh_button_layout(B,A)
		if B.state is CoreState.running:B.async_create_task(N())
		else:A.async_on_unload(B.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED,N))
	G=_build_buttons_from_options(A.options.get(_Z,{}));S={_K:A.title,CONF_DEVICE_SERIAL:A.data.get(CONF_DEVICE_SERIAL,''),CONF_DEVICE_NAME:A.data.get(CONF_DEVICE_NAME,''),CONF_AREA_NAME:A.data.get(CONF_AREA_NAME,''),CONF_KEYPAD_TYPE:A.data.get(CONF_KEYPAD_TYPE,_t),_E:A.data.get(_E,''),_W:A.data.get(_W,[]),_w:A.data.get(_w,[]),_x:A.data.get(_x),_y:A.data.get(_y),_z:A.data.get(_z,{}),_k:A.data.get(_k,{}),CONF_BUTTONS:G};F=LutronKeypadsController(B,S,config_entry=A)
	if G:F.async_register();_LOGGER.info("Keypad '%s' loaded from UI options with %d button(s)",A.title,len(G))
	else:_LOGGER.info("Keypad '%s' loaded (no buttons configured yet). Click the gear icon to configure buttons, or add YAML under lutron_keypad_controller:",A.title)
	B.data[DOMAIN][_l][A.entry_id]=F;B.data[DOMAIN][_o].append(F)
	if not B.services.has_service(DOMAIN,_A5):B.services.async_register(DOMAIN,_A5,_async_debug_leds)
	await F.async_initialize();await _cleanup_orphaned_entities(B,A);await B.config_entries.async_forward_entry_setups(A,PLATFORMS);B.async_create_background_task(periodic_revocation_check(B,C.jti,A.entry_id,instance_id=E),name=f"lutron_keypad_license_check_{A.entry_id}");return _B
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
	if B.data.get(_m):return await A.config_entries.async_unload_platforms(B,[_O])
	D=await A.config_entries.async_unload_platforms(B,PLATFORMS);C=A.data[DOMAIN].get(_l,{}).pop(B.entry_id,_A)
	if C is not _A:
		C.async_unregister()
		try:A.data[DOMAIN][_o].remove(C)
		except ValueError:pass
	return D
async def _async_reload_entry(hass,entry):await hass.config_entries.async_reload(entry.entry_id)
def _normalize_led_map(raw_led_map,config_entry):
	F='number';C=config_entry;A=raw_led_map
	if not A:return A
	G=C.data;D=get_button_list(G.get(CONF_KEYPAD_TYPE,KEYPAD_GENERIC));H={A[F]for A in D}
	if any(A in H for A in A):return A
	I=sorted(A[F]for A in D if not A['is_raise']and not A['is_lower']);E=sorted(A.keys());B={}
	for(J,K)in zip(I,E):B[J]=A[K]
	_LOGGER.info("'%s': LED map: LEAP global IDs %s → sequential button numbers %s",C.title,E,list(B.keys()));return B
class LutronKeypadsController:
	def __init__(A,hass,config,config_entry=_A):
		C=config_entry;B=config;A.hass=hass;A.name=B[_K];A.serial=str(B.get(CONF_DEVICE_SERIAL,'')).strip();A.device_id=str(B.get(_E,'')).strip();A.device_name=B.get(CONF_DEVICE_NAME,'').strip().lower();A.area_name=B.get(CONF_AREA_NAME,'').strip().lower();A.keypad_type=B.get(CONF_KEYPAD_TYPE,_t);A.scene_group=B.get(_L,'').strip();A._config_entry=C;A._buttons={}
		for D in B.get(CONF_BUTTONS,[]):A._buttons[D[CONF_BUTTON_NUMBER]]=D
		A._active_scene_btn=_A;A._last_action=_A;A._cover_states={};A._light_dim_indices={};A._unsubscribe=_A;A._led_map={};A._button_switches={};A._leap_btn_map={}
		if C is not _A:E=C.data.get(_k,{});A._leap_btn_map={int(A):B for(A,B)in E.items()}
		A._press_times={};A._last_press_times={};A._last_dispatch_times={};A._held={};A._confirm_handles={};A._ramp_tasks={};A._ramp_dirs={};A._ramp_end_times={};A._state_sensors=[];A._entity_tracking_unsubs=[]
	@callback
	def async_register(self):A=self;A._unsubscribe=A.hass.bus.async_listen(LUTRON_EVENT,A._handle_event);_LOGGER.info("Lutron Keypad Controller '%s' registered (serial=%s)",A.name,A.serial)
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
				J=str(B.get(_J,''));K=str(B.get(_E,''))
				if J!=A.serial and K!=A.device_id:continue
				C+=1;D=_A
				for L in(_a,_b):
					G=B.get(L)
					if G is not _A:
						try:D=int(G);break
						except(TypeError,ValueError):pass
				H=B.get(_b)
				if D is not _A and H is not _A:
					try:A._leap_btn_map[int(H)]=D
					except(TypeError,ValueError):pass
			if C>0:_LOGGER.debug("'%s': _build_leap_btn_map — matched %d entries on bridge, map=%s",A.name,C,A._leap_btn_map);return
		if not E:_LOGGER.warning("'%s': _build_leap_btn_map — no lutron_caseta bridge found; raise/lower LEAP remapping unavailable.",A.name)
		else:_LOGGER.debug("'%s': _build_leap_btn_map — no bridge had this serial in button_devices (expected for Caseta Pro).",A.name)
	async def async_initialize(A):
		if A._config_entry is _A:return
		await A._build_leap_btn_map();B=await _find_led_entities_by_button_entities(A.hass,A._config_entry)
		if not B:_LOGGER.debug("'%s': button-entity LED discovery found nothing — trying registry scan",A.name);B=await _find_led_entities(A.hass,A._config_entry)
		if B:A._led_map=_normalize_led_map(B,A._config_entry);_LOGGER.warning("'%s': LED map ready (keys = sequential button numbers): %s",A.name,A._led_map)
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
	def _update_room_mode_led(self,btn_num,entities):B=btn_num;A=self;C=any((D:=A.hass.states.get(B))is not _A and D.state not in(_f,_p,_q,_d,_c)for B in entities);A._update_button_switch_state(B,C);A.hass.async_create_task(A._write_led_entity(B,C))
	@callback
	def _update_pathway_mode_led(self,btn_num,entities):C=entities;B=btn_num;A=self;D=bool(C)and all((E:=A.hass.states.get(B))is not _A and E.state not in(_f,_p,_q,_d,_c)for B in C);A._update_button_switch_state(B,D);A.hass.async_create_task(A._write_led_entity(B,D))
	@callback
	def _update_scene_mode_led(self,btn_num,entities):
		D=entities;B=btn_num;A=self;C=A._buttons.get(B,{});I=int(C.get(CONF_TARGET_BRIGHTNESS)or 0);J=int(C.get(CONF_TARGET_COLOR_TEMP)or 0);K=C.get(CONF_ENTITY_SETTINGS,{})
		def F(eid):
			D=eid;B=A.hass.states.get(D)
			if B is _A or B.state in(_f,_p,_q,_d,_c):return _C
			if not D.startswith(_N):return _B
			E=K.get(D,{});F=int(E.get(_G)or I);G=int(E.get(_T)or J)
			if F>0:
				L=round((B.attributes.get(_G,0)or 0)/255*100)
				if abs(L-F)>5:return _C
			if G>0:
				C=B.attributes.get(_A6)
				if C is _A:
					H=B.attributes.get(_T)
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
		F=SERVICE_TURN_ON if C else SERVICE_TURN_OFF
		try:await A.hass.services.async_call(_O,F,{ATTR_ENTITY_ID:D},blocking=_B);_LOGGER.debug("'%s': button %d LED '%s' → %s",A.name,B,D,'ON'if C else'OFF')
		except Exception as G:_LOGGER.warning("'%s': button %d could not write LED entity '%s': %s",A.name,B,D,G)
	async def _write_group_leds(A,active_btn,active_btn_cfg):
		C=active_btn_cfg.get(_L)or A.scene_group
		for(B,D)in A._buttons.items():
			if D.get(CONF_ACTION_TYPE)!=ACTION_STATEFUL_SCENE:continue
			if not A._get_led_entity(B):continue
			E=D.get(_L)or A.scene_group
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
		B=event_data;C=str(B.get(_E,'')).strip()
		if C and A.device_id and C==A.device_id:return _B
		if A.serial:
			D=str(B.get(_J,'')).strip()
			if D and D==str(A.serial):return _B
		E=str(B.get('device_name','')).lower();F=str(B.get(_A2,'')).lower()
		if A.device_name and A.area_name:return E==A.device_name and F==A.area_name
		if A.device_name:return E==A.device_name
		if A.area_name:return F==A.area_name
		return _C
	@callback
	def _handle_event(self,event):
		H='action';A=self;B=event.data;_LOGGER.debug("'%s': event received — serial=%s device_id=%s btn=%s leap_btn=%s action=%s",A.name,B.get(_J),B.get(_E),B.get(_a),B.get(_b),B.get(H))
		if not A._matches_event(B):_LOGGER.debug("'%s': ignoring event — ev serial=%s device_id=%s / our serial=%s device_id=%s",A.name,B.get(_J),B.get(_E),A.serial,A.device_id);return
		E=B.get(_a)
		if E is _A:
			F=B.get(_b)
			if F is _A:_LOGGER.debug("'%s': event has no button_number or leap_button_number: %s",A.name,B);return
			E=int(F)
		C=A._leap_btn_map.get(int(E),int(E));_LOGGER.debug("'%s': matched — resolved btn_num=%d, configured buttons=%s",A.name,C,list(A._buttons.keys()));D=A._buttons.get(C)
		if D is _A:
			G=A._try_auto_map_raise_lower(C)
			if G is not _A:C=G;D=A._buttons.get(C)
		if D is _A:_LOGGER.debug("'%s': button %d pressed but not configured — ignoring",A.name,C);return
		I=B.get(H,'press')
		if I=='release':A._handle_release(C);return
		_LOGGER.info("'%s': button %d (%s) pressed — action_type=%s",A.name,C,D.get(CONF_BUTTON_LABEL,''),D[CONF_ACTION_TYPE]);A._on_press(C,D)
	_HOLD_CONFIRM=.3;_HOLD_CONFIRM_CYCLE=.7;_PRESS_DEBOUNCE=.2;_DOUBLE_TAP_WINDOW=.4;_RAMP_STEP_PCT=10;_RAMP_INTERVAL=.4;_HOLD_ACTIONS=frozenset({ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION,ACTION_STATEFUL_SCENE,ACTION_RAISE,ACTION_LOWER,ACTION_LIGHT_CYCLE_DIM})
	@callback
	def _on_press(self,btn_num,btn_cfg):
		C=btn_cfg;B=btn_num;A=self;D=asyncio.get_event_loop().time();F=A._last_dispatch_times.get(B,0)
		if D-F<A._PRESS_DEBOUNCE:_LOGGER.debug("'%s': button %d press ignored — %.0fms since last dispatch (debounce)",A.name,B,(D-F)*1000);return
		G=A._confirm_handles.pop(B,_A)
		if G is not _A:G.cancel()
		E=A._ramp_tasks.pop(B,_A)
		if E is not _A and not E.done():E.cancel()
		H=A._last_press_times.get(B,0);A._last_press_times[B]=D;A._press_times[B]=D;A._held[B]=_C;I=C.get(_j,{});J=I.get(_v,{})
		if D-H<A._DOUBLE_TAP_WINDOW and J.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE:_LOGGER.info("'%s': button %d DOUBLE TAP (%.3fs since last press)",A.name,B,D-H);L=A._merge_v2_block(C,J);A.hass.async_create_task(A._dispatch(B,L));return
		K=C.get(CONF_ACTION_TYPE);M=I.get(_i,{});N=M.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE and not C.get(_Q,_C);O=K in A._HOLD_ACTIONS or C.get(_Q,_C)or N
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
		F=C.get(CONF_ACTION_TYPE);H=C.get(_Q,_C);I=C.get(_j,{});G=I.get(_i,{})
		if not H and G.get(CONF_ACTION_TYPE,ACTION_NONE)!=ACTION_NONE:_LOGGER.info("'%s': button %d HOLD — dispatching custom hold action '%s'",A.name,B,G.get(CONF_ACTION_TYPE));A._held[B]=_B;J=A._merge_v2_block(C,G);A.hass.async_create_task(A._dispatch(B,J));return
		if F==ACTION_RAISE:E=_g;D=A._get_last_ramp_lights()
		elif F==ACTION_LOWER:E=_U;D=A._get_last_ramp_lights()
		elif F==ACTION_LIGHT_CYCLE_DIM or H:D=A._get_btn_light_entities(C);E=A._next_ramp_dir(B,D);_LOGGER.info("'%s': button %d HOLD — cycle_dim ramp %s on %s",A.name,B,E,D)
		else:
			if not A._is_btn_led_on(B):_LOGGER.debug("'%s': button %d hold event — LED off, dispatching instead",A.name,B);A._held[B]=_B;A.hass.async_create_task(A._dispatch(B,C));return
			D=A._get_btn_light_entities(C);E=A._next_ramp_dir(B,D)
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
					if E.state==_f:
						if C==_g:await A.hass.services.async_call(_H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_V:1},blocking=_C);D=_C
						continue
					F=round((E.attributes.get(_G,0)or 0)/255*100);G=min(100,F+A._RAMP_STEP_PCT)if C==_g else max(0,F-A._RAMP_STEP_PCT)
					if G==F:continue
					D=_C
					if C==_U and G<=0:await A.hass.services.async_call(_H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_C)
					else:await A.hass.services.async_call(_H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_V:G,_r:A._RAMP_INTERVAL},blocking=_C)
				if D:break
				await asyncio.sleep(A._RAMP_INTERVAL)
		except asyncio.CancelledError:pass
		finally:A._ramp_tasks.pop(btn_num,_A)
	_RAMP_DIR_RESET_WINDOW=5.
	def _next_ramp_dir(A,btn_num,entities=_A):
		D=entities;C=btn_num;F=asyncio.get_event_loop().time();E=A._ramp_end_times.get(C)
		if E is _A or F-E>A._RAMP_DIR_RESET_WINDOW:
			if D and all(A._light_at_max(B)for B in D):B=_U
			else:B=_g
		else:G=A._ramp_dirs.get(C,_U);B=_g if G==_U else _U
		A._ramp_dirs[C]=B;return B
	def _light_at_max(B,eid):
		A=B.hass.states.get(eid)
		if A is _A or A.state!='on':return _C
		return round((A.attributes.get(_G,0)or 0)/255*100)>=99
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
		if A.get(_L):B[_L]=A[_L]
		return B
	def _get_btn_light_entities(E,btn_cfg):
		A=btn_cfg;B=A.get(CONF_ACTION_TYPE)
		if B in(ACTION_ENTITY_TOGGLE,ACTION_SINGLE_ACTION,ACTION_LIGHT_CYCLE_DIM):return[A for A in _normalize_targets(A.get(CONF_ACTION_TARGET,[]))if A.startswith(_N)]
		if B==ACTION_STATEFUL_SCENE:
			C=A.get(CONF_ACTION_TARGET,'');D=E.hass.states.get(C)if C else _A
			if D:return[A for A in D.attributes.get(_AA,[])if A.startswith(_N)]
		if A.get(_Q,_C):return[A for A in _normalize_targets(A.get(CONF_ACTION_TARGET,[]))if A.startswith(_N)]
		return[]
	def _scene_light_entities(B,scene_id):
		A=B.hass.states.get(scene_id)
		if A is _A:return[]
		return[A for A in A.attributes.get(_AA,[])if A.startswith(_N)]
	def _get_last_ramp_lights(A):
		if A._last_action is _A:return[]
		B=A._last_action.get(_I,[])
		if B:return[A for A in B if A.startswith(_N)]
		D=A._last_action.get(_D)
		if D in(ACTION_STATEFUL_SCENE,ACTION_HA_SCENE):C=A._last_action.get(_s,'');return A._scene_light_entities(C)if C else[]
		return[]
	async def _dispatch(A,btn_num,btn_cfg):
		X='delay';W='fade';G=btn_cfg;C=btn_num;F=G[CONF_ACTION_TYPE];I=G.get(CONF_ACTION_TARGET);S=G.get(CONF_ACTION_PARAMS,{})
		if F==ACTION_NONE:return
		elif F==ACTION_HA_SCENE:await A._activate_scene(I);await A._write_led_entity(C,_B);A._last_action={_D:ACTION_HA_SCENE,_s:I}
		elif F==ACTION_STATEFUL_SCENE:await A._activate_stateful_scene(C,G,I)
		elif F==ACTION_AUTOMATION:await A._trigger_automation(I);await A._write_led_entity(C,_B)
		elif F==ACTION_SCRIPT:await A._run_script(I,S);await A._write_led_entity(C,_B)
		elif F==ACTION_ENTITY_TOGGLE:
			D=_normalize_targets(I);O=int(G.get(CONF_TARGET_BRIGHTNESS)or 0);P=int(G.get(CONF_TARGET_COLOR_TEMP)or 0);J=G.get(CONF_ENTITY_SETTINGS,{});Z=G.get(CONF_LED_MODE,LED_MODE_ROOM);a=G.get(_j,{});b=a.get(_u,{});U=b.get('entity_settings',{})
			if Z==LED_MODE_SCENE:
				if A._is_btn_led_on(C):
					_LOGGER.info("'%s': button %d PRESS OFF (scene mode) — LED was ON, applying off_level to %s",A.name,C,D)
					for B in D:
						H=B.split(_S)[0];V=U.get(B,{});K=int(V.get(_G)or 0)
						if H==_H and K>0:_LOGGER.info("'%s': button %d  → %s dim to %d%%",A.name,C,B,K);await A.hass.services.async_call(_H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_V:K},blocking=_B)
						else:_LOGGER.info("'%s': button %d  → %s turn OFF",A.name,C,B);await A.hass.services.async_call(H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_I:D};await A._write_led_entity(C,_C)
				else:
					_LOGGER.info("'%s': button %d PRESS ON (scene mode) — LED was OFF, activating scene on %s",A.name,C,D)
					for B in D:
						if B.startswith(_N):E=J.get(B,{});L=int(E.get(_G)or O);M=int(E.get(_T)or P);Q=E.get(_h);N=float(E.get(W)or 0);R=float(E.get(X)or 0);_LOGGER.info("'%s': button %d  → %s bri=%d%% cct=%dK fade=%.1fs",A.name,C,B,L,M,N);await A._apply_light_settings(B,L,M,Q,N,R)
						else:H=B.split(_S)[0];await A.hass.services.async_call(H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_I:D}
			else:
				T=_C
				if D:Y=A.hass.states.get(D[0]);T=Y is not _A and Y.state not in(_f,_p,_q,_d,_c)
				c=any(int(J.get(A,{}).get(_G)or O)>0 or int(J.get(A,{}).get(_T)or P)>0 or bool(J.get(A,{}).get(_h))for A in D if A.startswith(_N))if D else _C
				if not T and c:
					for B in D:
						if B.startswith(_N):E=J.get(B,{});L=int(E.get(_G)or O);M=int(E.get(_T)or P);Q=E.get(_h);N=float(E.get(W)or 0);R=float(E.get(X)or 0);await A._apply_light_settings(B,L,M,Q,N,R)
						else:H=B.split(_S)[0];await A.hass.services.async_call(H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_I:D};await A._write_led_entity(C,_B)
				elif T and U:
					for B in D:
						H=B.split(_S)[0];V=U.get(B,{});K=int(V.get(_G)or 0)
						if H==_H and K>0:await A.hass.services.async_call(_H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_V:K},blocking=_B)
						else:await A.hass.services.async_call(H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_B)
					A._last_action={_D:ACTION_ENTITY_TOGGLE,_I:D};await A._write_led_entity(C,_C)
				else:await A._entity_toggle(I);await A._write_led_entity(C,not T)
		elif F==ACTION_SINGLE_ACTION:
			D=_normalize_targets(I);O=int(G.get(CONF_TARGET_BRIGHTNESS)or 0);P=int(G.get(CONF_TARGET_COLOR_TEMP)or 0);J=G.get(CONF_ENTITY_SETTINGS,{});_LOGGER.info("'%s': button %d SINGLE ACTION — activating %s",A.name,C,D)
			for B in D:
				if B.startswith(_N):E=J.get(B,{});L=int(E.get(_G)or O);M=int(E.get(_T)or P);Q=E.get(_h);N=float(E.get(W)or 0);R=float(E.get(X)or 0);await A._apply_light_settings(B,L,M,Q,N,R)
				else:H=B.split(_S)[0];await A.hass.services.async_call(H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B},blocking=_B)
			A._last_action={_D:ACTION_SINGLE_ACTION,_I:D}
		elif F==ACTION_COVER_CYCLE:await A._cover_cycle(C,I)
		elif F==ACTION_LIGHT_CYCLE_DIM:d=S.get('levels',DIM_CYCLE_LEVELS);await A._light_cycle_dim(C,I,d)
		elif F==ACTION_RAISE:await A._raise(S)
		elif F==ACTION_LOWER:await A._lower(S)
		else:_LOGGER.error("'%s': unknown action_type '%s'",A.name,F);return
		if A._last_action is not _A and F not in(ACTION_RAISE,ACTION_LOWER):A._last_action[_A0]=C
		A._notify_state_sensors()
	async def _apply_light_settings(E,eid,bri,cct,hs_color=_A,fade=0,delay=0):
		H=delay;G=hs_color;F=eid;D=cct;C=bri;A=fade
		if H>0:await asyncio.sleep(H)
		if C>0 and D>0:
			I={ATTR_ENTITY_ID:F,_A6:D}
			if A>0:I[_r]=A
			await E.hass.services.async_call(_H,SERVICE_TURN_ON,I,blocking=_B);J={ATTR_ENTITY_ID:F,_V:C}
			if A>0:J[_r]=A
			await E.hass.services.async_call(_H,SERVICE_TURN_ON,J,blocking=_B)
		else:
			B={ATTR_ENTITY_ID:F}
			if C>0:B[_V]=C
			if D>0:B[_A6]=D
			if G:B[_h]=G
			if A>0:B[_r]=A
			await E.hass.services.async_call(_H,SERVICE_TURN_ON,B,blocking=_B)
	async def _activate_scene(B,scene_id):A=scene_id;await B.hass.services.async_call('scene','turn_on',{ATTR_ENTITY_ID:A},blocking=_B);_LOGGER.debug('Scene activated: %s',A)
	async def _activate_stateful_scene(A,btn_num,btn_cfg,scene_id):
		D=btn_cfg;C=scene_id;B=btn_num;await A._activate_scene(C);A._active_scene_btn=B;E=D.get(_L)or A.scene_group
		if E:_SCENE_GROUPS[E]=B
		await A._sync_leds(B);await A._write_group_leds(B,D);A._last_action={_D:ACTION_STATEFUL_SCENE,_s:C,_A0:B};_LOGGER.debug("Stateful scene '%s' activated on btn %d",C,B)
	async def _trigger_automation(A,automation_id):B=automation_id;await A.hass.services.async_call('automation','trigger',{ATTR_ENTITY_ID:B,'skip_condition':_B},blocking=_B);A._last_action={_D:ACTION_AUTOMATION,_F:B}
	async def _run_script(B,script_id,params):
		D=params;C=script_id;A='variables';E={ATTR_ENTITY_ID:C}
		if A in D:E[A]=D[A]
		await B.hass.services.async_call('script','turn_on',E,blocking=_C);B._last_action={_D:ACTION_SCRIPT,_F:C}
	async def _entity_toggle(A,targets):
		B=_normalize_targets(targets)
		for C in B:D=C.split(_S)[0];await A.hass.services.async_call(D,SERVICE_TOGGLE,{ATTR_ENTITY_ID:C},blocking=_B)
		A._last_action={_D:ACTION_ENTITY_TOGGLE,_I:B}
	async def _cover_cycle(B,btn_num,targets):
		F=btn_num;C=_normalize_targets(targets);D=B._cover_states.get(F,COVER_STATE_CLOSE)
		if D==COVER_STATE_CLOSE:A=COVER_STATE_OPEN;E=_AB
		elif D==COVER_STATE_OPEN:A=COVER_STATE_STOP;E='stop_cover'
		else:A=COVER_STATE_CLOSE;E=_AC
		B._cover_states[F]=A;await B.hass.services.async_call(_A7,E,{ATTR_ENTITY_ID:C},blocking=_B);B._last_action={_D:ACTION_COVER_CYCLE,_I:C,'state':A};_LOGGER.debug('Cover cycle: %s → %s on %s',D,A,C)
	async def _light_cycle_dim(A,btn_num,targets,levels):
		E=btn_num;D=levels;B=_normalize_targets(targets);C=A._light_dim_indices.get(E,len(D))
		if C>=len(D):C=0
		else:C+=1
		if C>=len(D):await A.hass.services.async_call(_H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:B},blocking=_B);A._light_dim_indices[E]=len(D);A._last_action={_D:ACTION_LIGHT_CYCLE_DIM,_I:B,_G:0};_LOGGER.debug('Light cycle: turned off %s',B)
		else:F=D[C];G=int(F/100*255);await A.hass.services.async_call(_H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:B,_G:G},blocking=_B);A._light_dim_indices[E]=C;A._last_action={_D:ACTION_LIGHT_CYCLE_DIM,_I:B,_G:F};_LOGGER.debug('Light cycle: %s → %d%%',B,F)
	def _last_action_light_entities(A):
		if A._last_action is _A:return[]
		B=A._last_action.get(_I,[])
		if B:return[A for A in B if A.startswith(_N)]
		D=A._last_action.get(_D)
		if D in(ACTION_STATEFUL_SCENE,ACTION_HA_SCENE):C=A._last_action.get(_s,'');return A._scene_light_entities(C)if C else[]
		return[]
	async def _raise(A,params):
		if A._last_action is _A:_LOGGER.debug("'%s': RAISE pressed but no prior context",A.name);return
		D=A._last_action;F=D.get(_D);B=D.get(_I,[])
		if F==ACTION_COVER_CYCLE or _entities_are_covers(B):
			await A.hass.services.async_call(_A7,_AB,{ATTR_ENTITY_ID:B},blocking=_B)
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
		D=A._last_action;F=D.get(_D);B=D.get(_I,[])
		if F==ACTION_COVER_CYCLE or _entities_are_covers(B):
			await A.hass.services.async_call(_A7,_AC,{ATTR_ENTITY_ID:B},blocking=_B)
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
			G=A.split(_S)[0]
			if G!=_H:continue
			H=C.attributes.get(_G,0)or 0;D=round(H/255*100);E=max(0,min(100,D+delta_pct));F=int(E/100*255)
			if F<=0:await B.hass.services.async_call(_H,SERVICE_TURN_OFF,{ATTR_ENTITY_ID:A},blocking=_B)
			else:await B.hass.services.async_call(_H,SERVICE_TURN_ON,{ATTR_ENTITY_ID:A,_G:F},blocking=_B)
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