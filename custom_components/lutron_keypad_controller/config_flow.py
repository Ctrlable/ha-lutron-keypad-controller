from __future__ import annotations
_A0='led_bindings'
_z='Keypad'
_y='license'
_x='device_not_found'
_w='already_configured'
_v='lutron_not_loaded'
_u='model_number'
_t='lutron_lip'
_s='remote'
_r='hybrid'
_q='alisee'
_p='scene_group'
_o='keypad_name'
_n='is_lower'
_m='is_raise'
_l='value'
_k='lutron_type'
_j='caseta'
_i='model'
_h='leap_button_map'
_g='-down'
_f=' down'
_e='-lower'
_d=' lower'
_c='-up'
_b=' up'
_a='-raise'
_Z=' raise'
_Y='leap_button_number'
_X='button_number'
_W='pico'
_V='tabletop'
_U='seetouch'
_T='sunnata'
_S='palladiom'
_R='lip'
_Q='lower_button'
_P='raise_button'
_O='configurable_buttons'
_N='area_name'
_M='lutron_caseta'
_L='unique_id'
_K='button_numbers'
_J='keypad'
_I='button_names'
_H='type'
_G='device_id'
_F='buttons'
_E='number'
_D='serial'
_C='label'
_B='name'
_A=None
import logging,re
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant,callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import area_registry as ar,device_registry as dr,entity_registry as er,selector
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
import homeassistant.helpers.config_validation as cv
from.const import DOMAIN,ACTION_ENTITY_TOGGLE,CONF_DEVICE_SERIAL,CONF_DEVICE_NAME,CONF_AREA_NAME,CONF_KEYPAD_TYPE,CONF_ACTION_TYPE,CONF_ACTION_TARGET,CONF_LED_ENTITY,CONF_LED_INVERT,CONF_LED_MODE,CONF_TARGET_BRIGHTNESS,CONF_TARGET_COLOR_TEMP,LED_MODE_ROOM,LED_MODE_SCENE,ACTION_STATEFUL_SCENE,KEYPAD_SEETOUCH,KEYPAD_SEETOUCH_HYBRID,KEYPAD_SUNNATA,KEYPAD_SUNNATA_HYBRID,KEYPAD_ALISEE,KEYPAD_PALLADIOM,KEYPAD_TABLETOP,KEYPAD_PICO,KEYPAD_GENERIC,ACTION_NONE,ACTION_RAISE,ACTION_LOWER,ACTION_TYPE_LABELS,ACTION_TYPE_DOMAINS,ACTION_TYPES_NEEDING_ENTITY,MULTI_ENTITY_ACTIONS,get_button_list,get_button_layout
_LOGGER=logging.getLogger(__name__)
LUTRON_TYPE_MAP={'SeeTouchKeypad':KEYPAD_SEETOUCH,'SeeTouchHybridKeypad':KEYPAD_SEETOUCH_HYBRID,'HybridSeeTouch':KEYPAD_SEETOUCH_HYBRID,'HybridSeeTouchKeypad':KEYPAD_SEETOUCH_HYBRID,'SeeTouch':KEYPAD_SEETOUCH,'SunnataKeypad':KEYPAD_SUNNATA,'SunnataHybridKeypad':KEYPAD_SUNNATA_HYBRID,'SunnataSwitchingKeypad':KEYPAD_SUNNATA,'Sunnata':KEYPAD_SUNNATA,'AlisseKeypad':KEYPAD_ALISEE,'AlisseSeeTouchKeypad':KEYPAD_ALISEE,'Alisse':KEYPAD_ALISEE,'AliseeKeypad':KEYPAD_ALISEE,'AliseeSeeTouchKeypad':KEYPAD_ALISEE,'Alisee':KEYPAD_ALISEE,'GrafikEyeQS':KEYPAD_ALISEE,'GRAFIK Eye QS':KEYPAD_ALISEE,'PalladiomKeypad':KEYPAD_PALLADIOM,'PalladiomKeypad2Button':KEYPAD_PALLADIOM,'PalladiomKeypad3Button':KEYPAD_PALLADIOM,'PalladiomKeypad4Button':KEYPAD_PALLADIOM,'PalladiomKeypad5Button':KEYPAD_PALLADIOM,'PalladiomKeypad7Button':KEYPAD_PALLADIOM,'Palladiom':KEYPAD_PALLADIOM,'PalladiomWirelessKeypad':KEYPAD_PALLADIOM,'PalladiomSeeTouchKeypad':KEYPAD_PALLADIOM,'PalladiomHybridKeypad':KEYPAD_PALLADIOM,'TabletopSeeTouch':KEYPAD_TABLETOP,'SeeTouchTabletop':KEYPAD_TABLETOP,'TabletopKeypad':KEYPAD_TABLETOP,'Pico1Button':KEYPAD_PICO,'Pico2Button':KEYPAD_PICO,'Pico2ButtonRaiseLower':KEYPAD_PICO,'Pico3Button':KEYPAD_PICO,'Pico3ButtonRaiseLower':KEYPAD_PICO,'Pico4Button':KEYPAD_PICO,'Pico4ButtonScene':KEYPAD_PICO,'Pico4ButtonZone':KEYPAD_PICO,'Pico4Button2Group':KEYPAD_PICO,'FourGroupRemote':KEYPAD_PICO,'PaddleRemote':KEYPAD_PICO}
LUTRON_TYPE_FUZZY=[('aliss',KEYPAD_ALISEE),(_q,KEYPAD_ALISEE),(_S,KEYPAD_PALLADIOM),(_T,KEYPAD_SUNNATA),(_r,KEYPAD_SEETOUCH_HYBRID),(_U,KEYPAD_SEETOUCH),(_V,KEYPAD_TABLETOP),(_W,KEYPAD_PICO),(_s,KEYPAD_PICO),(_J,KEYPAD_SEETOUCH)]
BUTTON_TYPE_KEYWORDS={_J,_W,_s,_U,_T,'aliss',_q,_S,_V,_r}
def _infer_keypad_type(device_type):
	A=device_type
	if A in LUTRON_TYPE_MAP:return LUTRON_TYPE_MAP[A]
	C=A.lower()
	for(D,B)in LUTRON_TYPE_FUZZY:
		if D in C:_LOGGER.debug('Fuzzy-matched device type %r → %s',A,B);return B
	_LOGGER.warning('Unrecognized Lutron device type %r — falling back to generic keypad',A);return KEYPAD_GENERIC
def _is_keypad_device(device):
	A=device.get(_H,'')
	if A in LUTRON_TYPE_MAP:return True
	B=A.lower();return any(A in B for A in BUTTON_TYPE_KEYWORDS)
def _iter_lutron_bridges(hass):
	D='bridge'
	for C in hass.config_entries.async_entries(_M):
		if C.state is not ConfigEntryState.LOADED:continue
		E=getattr(C,'runtime_data',_A)
		if E is not _A:
			A=getattr(E,D,_A)
			if A is not _A:yield A;continue
		B=hass.data.get(_M,{}).get(C.entry_id)
		if B is not _A:
			A=getattr(B,D,_A)
			if A is _A and isinstance(B,dict):A=B.get(D)
			if A is not _A:yield A
def _get_lutron_bridge(hass):return next(_iter_lutron_bridges(hass),_A)
def _discover_keypads(hass):
	D=set();B=[]
	for E in _iter_lutron_bridges(hass):
		try:F=E.get_devices()
		except Exception as G:_LOGGER.warning('Could not query Lutron bridge devices: %s',G);continue
		for C in F.values():
			if not _is_keypad_device(C):continue
			A=str(C.get(_D,''))
			if A and A in D:continue
			B.append(C)
			if A:D.add(A)
	B.sort(key=lambda d:(d.get(_N,''),d.get(_B,'')));return B
def _build_device_options(keypads):
	B={}
	for A in keypads:
		C=str(A.get(_D,''))
		if not C:continue
		D=A.get(_N,'Unknown Area');E=A.get(_B,'Unknown');F=_infer_keypad_type(A.get(_H,''));B[C]=f"{D} — {E}  [{F}]"
	return B
def _resolve_btn_num(bd):
	for B in(_X,_Y):
		A=bd.get(B)
		if A is not _A:
			try:return int(A)
			except(TypeError,ValueError):pass
def _strip_engraving(full_name,area,device):
	D=device;C=full_name;A=C.strip()
	for B in[f"{area} {D}",D,area]:
		B=B.strip()
		if B and A.lower().startswith(B.lower()):A=A[len(B):].strip();break
	return A.title()if A else C.strip()
import re as _re_cf
_RAISE_NAME_RE=_re_cf.compile('\\braise\\b',_re_cf.IGNORECASE)
_LOWER_NAME_RE=_re_cf.compile('\\blower\\b',_re_cf.IGNORECASE)
def _build_layout_from_button_devices(candidates,area_name,device_name):
	I=candidates;B=sorted({O for A in I if(O:=_resolve_btn_num(A))is not _A})
	if not B:return{}
	C=_A;D=_A;F={};G={}
	for H in I:
		E=H.get(_B,'');J=E.lower();A=_resolve_btn_num(H);K=H.get(_Y)
		if A is not _A and K is not _A:
			try:
				L=int(K)
				if L!=A:G[str(L)]=A
			except(TypeError,ValueError):pass
		if A is _A:continue
		if J.endswith((_Z,_a,_b,_c))or _RAISE_NAME_RE.search(E):C=A
		elif J.endswith((_d,_e,_f,_g))or _LOWER_NAME_RE.search(E):D=A
		M=_strip_engraving(E,area_name,device_name)
		if M:F[str(A)]=M
	N=[A for A in B if A not in(C,D)];_LOGGER.debug('button_devices layout: %d total, configurable=%s raise=%s lower=%s names=%s leap_map=%s',len(B),N,C,D,F,G);return{_K:B,_O:N,_P:C,_Q:D,_I:F,_h:G}
def _build_layout_from_inline_buttons(buttons_list,area_name,device_name,device_full_name=''):
	A=[];C=_A;D=_A;F={};G={};O=device_name or device_full_name
	for H in buttons_list:
		I=H.get(_X)
		if I is _A:continue
		try:B=int(I)
		except(TypeError,ValueError):continue
		E=H.get(_B,'');J=E.lower()
		if J.endswith((_Z,_a,_b,_c))or _RAISE_NAME_RE.search(E):C=B
		elif J.endswith((_d,_e,_f,_g))or _LOWER_NAME_RE.search(E):D=B
		A.append(B);K=_strip_engraving(E,area_name,O)
		if K:F[str(B)]=K
		L=H.get(_Y)
		if L is not _A:
			try:
				M=int(L)
				if M!=B:G[str(M)]=B
			except(TypeError,ValueError):pass
	A=sorted(set(A));N=[A for A in A if A not in(C,D)];_LOGGER.debug('inline-buttons layout: %d total, configurable=%s raise=%s lower=%s names=%s leap_map=%s',len(A),N,C,D,F,G);return{_K:A,_O:N,_P:C,_Q:D,_I:F,_h:G}
def _build_layout_from_bridge_buttons(candidates,area_name,device_name,has_raise_lower=True):
	J=has_raise_lower;D=[];A=_A;B=_A;H={};I=[]
	for F in candidates:
		K=F.get(_X)
		if K is _A:continue
		try:E=int(K)
		except(TypeError,ValueError):continue
		G=F.get('button_name')or F.get(_B,'');L=G.lower();O=F.get('button_led')is not _A
		if J:
			if L.endswith((_Z,_a,_b,_c))or _RAISE_NAME_RE.search(G):A=E
			elif L.endswith((_d,_e,_f,_g))or _LOWER_NAME_RE.search(G):B=E
			elif not O:I.append(E)
		D.append(E);M=_strip_engraving(G,area_name,device_name)
		if M:H[str(E)]=M
	if J:
		for C in sorted(I):
			if C%2==1 and A is _A:A=C
			elif C%2==0 and B is _A:B=C
		for C in sorted(I):
			if A is _A and C!=B:A=C
			elif B is _A and C!=A:B=C
	D=sorted(set(D));N=[C for C in D if C not in(A,B)];_LOGGER.debug('bridge.buttons layout: %d total, configurable=%s raise=%s lower=%s names=%s',len(D),N,A,B,H);return{_K:D,_O:N,_P:A,_Q:B,_I:H,_h:{}}
def _detect_button_layout(hass,serial,keypad_type,device_name='',area_name='',device_id='',device_data=_A):
	H=area_name;G=device_name;C=device_id;A=serial
	for E in _iter_lutron_bridges(hass):
		F=getattr(E,'button_devices',_A)or{}
		if F:
			I=[B for B in F.values()if A and str(B.get(_D,''))==A or C and str(B.get(_G,''))==C]
			if I:_LOGGER.debug('Strategy 1 (button_devices): %d entries for serial=%s device_id=%s',len(I),A,C);return _build_layout_from_button_devices(I,H,G)
		B=device_data
		if B is _A:
			try:O=E.get_devices()
			except Exception as P:_LOGGER.warning('bridge.get_devices() failed during layout detection: %s',P);continue
			for J in O.values():
				if A and str(J.get(_D,''))==A or C and str(J.get(_G,''))==C:B=J;break
		if B is _A:continue
		D=str(B.get(_G,''))or C;_LOGGER.debug('Device serial=%s on bridge %s — type=%r model=%r device_id=%s inline_buttons=%d button_devices_total=%d',A,type(E).__name__,B.get(_H),B.get(_i),D,len(B.get(_F,[])),len(F));K=B.get(_F,[])
		if K:_LOGGER.debug('Strategy 2 (inline buttons): %d buttons for serial=%s',len(K),A);return _build_layout_from_inline_buttons(K,H,G,B.get(_B,''))
		L=getattr(E,_F,_A)or{}
		if L:
			M=[B for B in L.values()if A and str(B.get(_D,''))==A or D and str(B.get('parent_device',''))==D]
			if M:_LOGGER.debug('Strategy 3 (bridge.buttons): %d buttons for serial=%s device_id=%s',len(M),A,D);from.const import KEYPAD_LAYOUTS as N,KEYPAD_GENERIC as Q;S,R=N.get(keypad_type,N[Q]);return _build_layout_from_bridge_buttons(M,H,G,has_raise_lower=R)
		_LOGGER.warning('Device serial=%s (type=%r model=%r device_id=%s) found on bridge but carries no button data (button_devices=%d, inline_buttons=0, bridge.buttons=%d). Full device info: %s',A,B.get(_H),B.get(_i),D,len(F),len(L),B);return{}
	_LOGGER.debug('Device serial=%s device_id=%s not found on any bridge; falling back to keypad-type static layout.',A,C);return{}
def _infer_lip_keypad_type(model):
	A=(model or'').lower()
	if _S in A:return KEYPAD_PALLADIOM
	if _T in A:return KEYPAD_SUNNATA
	if _U in A or'see touch'in A:return KEYPAD_SEETOUCH
	if'alisse'in A or'alise'in A:return KEYPAD_ALISEE
	if _V in A or'table top'in A:return KEYPAD_TABLETOP
	if _W in A:return KEYPAD_PICO
	return KEYPAD_GENERIC
def _discover_lip_keypads(hass):
	H=hass;P=dr.async_get(H);Q=er.async_get(H);J=[]
	for A in P.devices.values():
		B=next((str(A[1])for A in A.identifiers if A[0]==_t),_A)
		if B is _A:continue
		C={}
		for E in er.async_entries_for_device(Q,A.id):
			if E.domain!='event':continue
			K=re.search('(\\d+)$',E.entity_id)
			if K:L=int(K.group(1));C[L]=E.original_name or E.name or f"Button {L}"
		if not C:continue
		F=sorted(C);M=18 if 18 in C else _A;N=19 if 19 in C else _A;R=[A for A in F if A not in(N,M)];I=A.model or'';G=''
		if A.area_id:
			O=ar.async_get(H).async_get_area(A.area_id)
			if O:G=O.name
		if A.name_by_user:D=A.name_by_user
		elif G:D=f"{G} keypad {B}"
		else:D=A.name or f"keypad {B}"
		J.append({_L:f"lip_{B}",_B:D,_C:f"{D} ({I or _J}, {len(F)} buttons)",'data':{_B:D,'backend':_R,'lip_id':B,_G:A.id,CONF_DEVICE_SERIAL:f"lip_{B}",CONF_DEVICE_NAME:D,CONF_AREA_NAME:G,CONF_KEYPAD_TYPE:_infer_lip_keypad_type(I),_u:I,_K:F,_I:{str(A):C[A]for A in F},_O:R,_P:N,_Q:M}})
	return sorted(J,key=lambda k:k[_B])
class LutronKeypadsConfigFlow(config_entries.ConfigFlow,domain=DOMAIN):
	VERSION=1
	def __init__(A):A._discovered_keypads=[];A._selected_device=_A;A._detected_layout={}
	async def async_step_user(A,user_input=_A):
		C=bool(A.hass.config_entries.async_entries(_M));B=bool(A.hass.config_entries.async_entries(_t))
		if not C and not B:return A.async_abort(reason=_v)
		if C and B:return await A.async_step_source()
		if B:return await A.async_step_lip()
		return await A.async_step_caseta()
	async def async_step_source(A,user_input=_A):
		C=user_input;B='source'
		if C is not _A:
			if C[B]==_R:return await A.async_step_lip()
			return await A.async_step_caseta()
		return A.async_show_form(step_id=B,data_schema=vol.Schema({vol.Required(B,default=_j):vol.In({_j:'Caséta / RA2 Select (lutron_caseta)',_R:'Homeworks QS / RadioRA (lutron_lip)'})}))
	async def async_step_lip(A,user_input=_A):
		D=user_input;F=_discover_lip_keypads(A.hass);G={A.unique_id or''for A in A.hass.config_entries.async_entries(DOMAIN)};B=[A for A in F if A[_L]not in G]
		if not B:return A.async_abort(reason=_w)
		E={}
		if D is not _A:
			H=D.get(_J);C=next((A for A in B if A[_L]==H),_A)
			if C is _A:E['base']=_x
			else:await A.async_set_unique_id(C[_L]);A._abort_if_unique_id_configured();return A.async_create_entry(title=C[_B],data=C['data'])
		return A.async_show_form(step_id=_R,data_schema=vol.Schema({vol.Required(_J):vol.In({A[_L]:A[_C]for A in B})}),errors=E,description_placeholders={'count':str(len(B))})
	async def async_step_caseta(A,user_input=_A):
		F='device_serial';C=user_input;G=A.hass.config_entries.async_entries(_M)
		if not G:return A.async_abort(reason=_v)
		if not A._discovered_keypads:A._discovered_keypads=await A.hass.async_add_executor_job(_discover_keypads,A.hass)
		if not A._discovered_keypads:return await A.async_step_manual()
		H={A.unique_id or''for A in A.hass.config_entries.async_entries(DOMAIN)};B=[A for A in A._discovered_keypads if str(A.get(_D,''))not in H]
		if not B:return A.async_abort(reason=_w)
		I=_build_device_options(B);D={}
		if C is not _A:
			E=C.get(F,'');A._selected_device=next((A for A in B if str(A.get(_D,''))==E),_A)
			if A._selected_device is _A:D['base']=_x
			else:await A.async_set_unique_id(E);A._abort_if_unique_id_configured();J=str(A._selected_device.get(_D,''));K=_infer_keypad_type(A._selected_device.get(_H,''));A._detected_layout=_detect_button_layout(A.hass,J,K,device_name=A._selected_device.get(_B,''),area_name=A._selected_device.get(_N,''),device_id=str(A._selected_device.get(_G,'')),device_data=A._selected_device);return await A.async_step_confirm()
		return A.async_show_form(step_id=_j,data_schema=vol.Schema({vol.Required(F):vol.In(I)}),errors=D,description_placeholders={'count':str(len(B))})
	async def async_step_confirm(B,user_input=_A):
		G=user_input;A=B._selected_device
		if A is _A:return await B.async_step_user()
		E=A.get(_H,'');F=_infer_keypad_type(E);C=A.get(_N,'');D=A.get(_B,'');H=str(A.get(_D,''));I=f"{C} — {D}"if C else D
		if G is not _A:J=G.get(_B,I).strip();return B.async_create_entry(title=J,data={_B:J,CONF_DEVICE_SERIAL:H,CONF_DEVICE_NAME:D,CONF_AREA_NAME:C,CONF_KEYPAD_TYPE:F,_k:E,_u:A.get(_i,''),_G:A.get(_G,''),**B._detected_layout})
		K=B._detected_layout.get(_K,[])
		if K:L=f"{len(K)} buttons detected from bridge"
		else:M=get_button_list(F);L=f"{len(M)} buttons (estimated from keypad type)"
		return B.async_show_form(step_id='confirm',data_schema=vol.Schema({vol.Required(_B,default=I):str}),description_placeholders={'area':C or'—','device_name':D,'keypad_type':F,_D:H,_k:E,'button_count':L})
	async def async_step_manual(B,user_input=_A):
		A=user_input;D={}
		if A is not _A:
			C=A.get(CONF_DEVICE_SERIAL,'').strip()
			if not C:D[CONF_DEVICE_SERIAL]='serial_required'
			else:await B.async_set_unique_id(C);B._abort_if_unique_id_configured();E=A.get(_B,C).strip();return B.async_create_entry(title=E,data={_B:E,CONF_DEVICE_SERIAL:C,CONF_DEVICE_NAME:A.get(CONF_DEVICE_NAME,''),CONF_AREA_NAME:A.get(CONF_AREA_NAME,''),CONF_KEYPAD_TYPE:KEYPAD_GENERIC,_k:''})
		return B.async_show_form(step_id='manual',data_schema=vol.Schema({vol.Required(_B):str,vol.Required(CONF_DEVICE_SERIAL):str,vol.Optional(CONF_DEVICE_NAME,default=''):str,vol.Optional(CONF_AREA_NAME,default=''):str}),errors=D,description_placeholders={'note':'Auto-discovery failed — the Lutron bridge may not be reachable yet. Enter the serial manually: press any button on the keypad and check Developer Tools → Events → lutron_caseta_button_event.'})
	async def async_step_panel(A,user_input=_A):
		B=user_input
		if not B:return A.async_abort(reason='no_data')
		C=str(B.get(CONF_DEVICE_SERIAL,'')).strip()
		if not C:return A.async_abort(reason='no_serial')
		await A.async_set_unique_id(C);A._abort_if_unique_id_configured();D=str(B.pop(_B,C)).strip()or C;return A.async_create_entry(title=D,data=B)
	async def async_step_controller(A,user_input=_A):await A.async_set_unique_id('controller');A._abort_if_unique_id_configured();return A.async_create_entry(title='Lutron Keypad Controller',data={'_controller':True})
	@staticmethod
	@callback
	def async_get_options_flow(config_entry):return LutronKeypadsOptionsFlow()
_ACTION_OPTIONS=[{_l:A,_C:B}for(A,B)in ACTION_TYPE_LABELS.items()]
class LutronKeypadsOptionsFlow(config_entries.OptionsFlow):
	def __init__(A):A._buttons_config={}
	def _get_all_buttons(A):return get_button_layout(A.config_entry.data)
	def _get_configurable(A):return[A for A in A._get_all_buttons()if not A[_m]and not A[_n]]
	def _get_raise_lower_note(C):
		A=[]
		for B in C._get_all_buttons():
			if B[_m]:A.append(f"Button {B[_E]} (Raise)")
			elif B[_n]:A.append(f"Button {B[_E]} (Lower)")
		if not A:return''
		return f"{", ".join(A)} are fixed raise/lower buttons and cannot be reassigned."
	def _get_led_bindings_note(C):
		B=C.hass.data.get(DOMAIN,{}).get('entry_controllers',{}).get(C.config_entry.entry_id)
		if B is _A or not B._led_map:return''
		D=['\n\n**Auto-discovered LED bindings:**']
		for A in sorted(B._led_map):E=B._buttons.get(A,{});F=C.config_entry.data.get(_I,{});G=E.get(_C)or C._buttons_config.get(A,{}).get(_C)or F.get(str(A))or f"Button {A}";D.append(f"- {G} (button #{A}) → `{B._led_map[A]}`")
		return'\n'.join(D)
	def _normalize_target(B,target):
		A=target
		if isinstance(A,list):return[str(A).strip()for A in A if str(A).strip()]
		if isinstance(A,str)and A.strip():return[A.strip()for A in A.split(',')if A.strip()]
		return[]
	def _default_entity(B,cfg,multiple):
		A=cfg.get(CONF_ACTION_TARGET,'')
		if multiple:return A if isinstance(A,list)else B._normalize_target(A)
		if isinstance(A,list):return A[0]if A else''
		return A or''
	async def async_step_init(A,user_input=_A):B=A.config_entry.entry_id;return A.async_show_menu(step_id='init',menu_options=[_F,_y],description_placeholders={'panel_url':f"/lutron-keypads?entry={B}",_o:A.config_entry.title})
	async def async_step_license(A,user_input=_A):
		C=user_input;B='license_key'
		if C is not _A:D=dict(A.config_entry.options);D[B]=C.get(B,'').strip();return A.async_create_entry(title='',data=D)
		E=await async_get_instance_id(A.hass);F=vol.Schema({vol.Optional(B,default=A.config_entry.options.get(B,'')):str});return A.async_show_form(step_id=_y,data_schema=F,description_placeholders={'instance_id':E})
	async def async_step_buttons(A,user_input=_A):
		D=user_input
		if not A._buttons_config:
			I=A.config_entry.options.get(_F,{})
			for(J,K)in I.items():
				try:A._buttons_config[int(J)]=dict(K)
				except(ValueError,TypeError):pass
		E=A._get_configurable();L=A.config_entry.data.get(_B,_z)
		if D is not _A:
			for C in E:
				B=C[_E];M=A._buttons_config.get(B,{});G=D.get(f"button_{B}_action_type",ACTION_NONE);A._buttons_config[B]={**M,_C:D.get(f"button_{B}_label",f"Button {B}"),CONF_ACTION_TYPE:G}
				if G not in ACTION_TYPES_NEEDING_ENTITY:A._buttons_config[B][CONF_ACTION_TARGET]=[];A._buttons_config[B][CONF_LED_ENTITY]='';A._buttons_config[B][_p]=''
			for C in A._get_all_buttons():
				if C[_m]:A._buttons_config[C[_E]]={_C:'Raise',CONF_ACTION_TYPE:ACTION_RAISE}
				elif C[_n]:A._buttons_config[C[_E]]={_C:'Lower',CONF_ACTION_TYPE:ACTION_LOWER}
			N=any(A._buttons_config.get(B[_E],{}).get(CONF_ACTION_TYPE)in ACTION_TYPES_NEEDING_ENTITY for B in E)
			if N:return await A.async_step_entities()
			return A.async_create_entry(title='',data={**A.config_entry.options,_F:{str(A):B for(A,B)in A._buttons_config.items()}})
		O=A.config_entry.data.get(_I,{});F={}
		for C in E:B=C[_E];H=A._buttons_config.get(B,{});P=O.get(str(B),f"Button {B}");F[vol.Optional(f"button_{B}_label",default=H.get(_C)or P)]=selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT));F[vol.Required(f"button_{B}_action_type",default=H.get(CONF_ACTION_TYPE,ACTION_NONE))]=selector.SelectSelector(selector.SelectSelectorConfig(options=_ACTION_OPTIONS,mode=selector.SelectSelectorMode.DROPDOWN))
		return A.async_show_form(step_id=_F,data_schema=vol.Schema(F),description_placeholders={_o:L,'raise_lower_note':A._get_raise_lower_note(),_A0:A._get_led_bindings_note()})
	async def async_step_entities(B,user_input=_A):
		K=False;C=user_input;M=B._get_configurable();I=[A for A in M if B._buttons_config.get(A[_E],{}).get(CONF_ACTION_TYPE)in ACTION_TYPES_NEEDING_ENTITY];N=B.config_entry.data.get(_B,_z)
		if not I:return B.async_create_entry(title='',data={**B.config_entry.options,_F:{str(A):B for(A,B)in B._buttons_config.items()}})
		if C is not _A:
			for J in I:
				A=J[_E];D=B._buttons_config[A][CONF_ACTION_TYPE];G=D in MULTI_ENTITY_ACTIONS;H=C.get(f"button_{A}_entity",[]if G else'');B._buttons_config[A][CONF_ACTION_TARGET]=(H if isinstance(H,list)else B._normalize_target(H))if G else H;B._buttons_config[A][CONF_LED_INVERT]=bool(C.get(f"button_{A}_led_invert",K))
				if D==ACTION_ENTITY_TOGGLE:B._buttons_config[A][CONF_LED_MODE]=C.get(f"button_{A}_led_mode",LED_MODE_ROOM);B._buttons_config[A][CONF_TARGET_BRIGHTNESS]=int(C.get(f"button_{A}_target_brightness")or 0);B._buttons_config[A][CONF_TARGET_COLOR_TEMP]=int(C.get(f"button_{A}_target_color_temp")or 0)
				if D==ACTION_STATEFUL_SCENE:B._buttons_config[A][CONF_LED_ENTITY]=C.get(f"button_{A}_led",'');L=C.get(f"button_{A}_scene_group",'');B._buttons_config[A][_p]=L.strip()if isinstance(L,str)else''
			return B.async_create_entry(title='',data={**B.config_entry.options,_F:{str(A):B for(A,B)in B._buttons_config.items()}})
		E={}
		for J in I:
			A=J[_E];F=B._buttons_config.get(A,{});D=F.get(CONF_ACTION_TYPE,ACTION_NONE);O=ACTION_TYPE_DOMAINS.get(D,[]);G=D in MULTI_ENTITY_ACTIONS;E[vol.Optional(f"button_{A}_entity",default=B._default_entity(F,G))]=selector.EntitySelector(selector.EntitySelectorConfig(domain=O,multiple=G))
			if D==ACTION_ENTITY_TOGGLE:E[vol.Optional(f"button_{A}_target_brightness",default=F.get(CONF_TARGET_BRIGHTNESS,0)or 0)]=selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=100,step=1,unit_of_measurement='%',mode='slider'));E[vol.Optional(f"button_{A}_target_color_temp",default=F.get(CONF_TARGET_COLOR_TEMP,0)or 0)]=selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=10000,step=100,unit_of_measurement='K',mode='box'));E[vol.Optional(f"button_{A}_led_mode",default=F.get(CONF_LED_MODE,LED_MODE_ROOM))]=selector.SelectSelector(selector.SelectSelectorConfig(options=[{_l:LED_MODE_ROOM,_C:'Room Mode — LED on when any entity is on'},{_l:LED_MODE_SCENE,_C:'Scene Mode — LED on when all entities match target'}],mode=selector.SelectSelectorMode.DROPDOWN))
			if D==ACTION_STATEFUL_SCENE:E[vol.Optional(f"button_{A}_led",default=F.get(CONF_LED_ENTITY,''))]=selector.EntitySelector(selector.EntitySelectorConfig(domain=['switch'],multiple=K));E[vol.Optional(f"button_{A}_scene_group",default=F.get(_p,''))]=selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT))
			E[vol.Optional(f"button_{A}_led_invert",default=F.get(CONF_LED_INVERT,K))]=selector.BooleanSelector()
		return B.async_show_form(step_id='entities',data_schema=vol.Schema(E),description_placeholders={_o:N,_A0:B._get_led_bindings_note()})