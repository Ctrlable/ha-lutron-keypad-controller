from __future__ import annotations
_A7='led_bindings'
_A6='lutron_not_loaded'
_A5='controller'
_A4='scene_group'
_A3='keypad_name'
_A2='is_lower'
_A1='is_raise'
_A0='value'
_z='lutron_type'
_y='count'
_x='device_not_found'
_w='base'
_v='already_configured'
_u='caseta'
_t='RFWC5'
_s='model_number'
_r='Lower'
_q='Raise'
_p='device_name'
_o='model'
_n='leap_button_map'
_m='-down'
_l=' down'
_k='-lower'
_j=' lower'
_i='-up'
_h=' up'
_g='-raise'
_f=' raise'
_e='leap_button_number'
_d='button_number'
_c='pico'
_b='tabletop'
_a='seetouch'
_Z='sunnata'
_Y='palladiom'
_X='rfwc5'
_W='lip'
_V='data'
_U='area'
_T='direction'
_S='lutron_lip'
_R='area_name'
_Q='lutron_caseta'
_P='engraving'
_O='lower_button'
_N='raise_button'
_M='configurable_buttons'
_L='button_numbers'
_K='button_names'
_J='device_id'
_I='type'
_H='keypad'
_G='unique_id'
_F='serial'
_E='number'
_D='buttons'
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
LUTRON_TYPE_FUZZY=[('aliss',KEYPAD_ALISEE),('alisee',KEYPAD_ALISEE),(_Y,KEYPAD_PALLADIOM),(_Z,KEYPAD_SUNNATA),('hybrid',KEYPAD_SEETOUCH_HYBRID),(_a,KEYPAD_SEETOUCH),(_b,KEYPAD_TABLETOP),(_c,KEYPAD_PICO),('remote',KEYPAD_PICO),(_H,KEYPAD_SEETOUCH)]
BUTTON_TYPE_KEYWORDS={_H,_c,'remote',_a,_Z,'aliss','alisee',_Y,_b,'hybrid'}
def _infer_keypad_type(device_type):
	A=device_type
	if A in LUTRON_TYPE_MAP:return LUTRON_TYPE_MAP[A]
	C=A.lower()
	for(D,B)in LUTRON_TYPE_FUZZY:
		if D in C:_LOGGER.debug('Fuzzy-matched device type %r → %s',A,B);return B
	_LOGGER.warning('Unrecognized Lutron device type %r — falling back to generic keypad',A);return KEYPAD_GENERIC
def _is_keypad_device(device):
	A=device.get(_I,'')
	if A in LUTRON_TYPE_MAP:return True
	B=A.lower();return any(A in B for A in BUTTON_TYPE_KEYWORDS)
def _iter_lutron_bridges(hass):
	D='bridge'
	for C in hass.config_entries.async_entries(_Q):
		if C.state is not ConfigEntryState.LOADED:continue
		E=getattr(C,'runtime_data',_A)
		if E is not _A:
			A=getattr(E,D,_A)
			if A is not _A:yield A;continue
		B=hass.data.get(_Q,{}).get(C.entry_id)
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
			A=str(C.get(_F,''))
			if A and A in D:continue
			B.append(C)
			if A:D.add(A)
	B.sort(key=lambda d:(d.get(_R,''),d.get(_B,'')));return B
def _build_device_options(keypads):
	B={}
	for A in keypads:
		C=str(A.get(_F,''))
		if not C:continue
		D=A.get(_R,'Unknown Area');E=A.get(_B,'Unknown');F=_infer_keypad_type(A.get(_I,''));B[C]=f"{D} — {E}  [{F}]"
	return B
def _resolve_btn_num(bd):
	for B in(_d,_e):
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
		E=H.get(_B,'');J=E.lower();A=_resolve_btn_num(H);K=H.get(_e)
		if A is not _A and K is not _A:
			try:
				L=int(K)
				if L!=A:G[str(L)]=A
			except(TypeError,ValueError):pass
		if A is _A:continue
		if J.endswith((_f,_g,_h,_i))or _RAISE_NAME_RE.search(E):C=A
		elif J.endswith((_j,_k,_l,_m))or _LOWER_NAME_RE.search(E):D=A
		M=_strip_engraving(E,area_name,device_name)
		if M:F[str(A)]=M
	N=[A for A in B if A not in(C,D)];_LOGGER.debug('button_devices layout: %d total, configurable=%s raise=%s lower=%s names=%s leap_map=%s',len(B),N,C,D,F,G);return{_L:B,_M:N,_N:C,_O:D,_K:F,_n:G}
def _build_layout_from_inline_buttons(buttons_list,area_name,device_name,device_full_name=''):
	A=[];C=_A;D=_A;F={};G={};O=device_name or device_full_name
	for H in buttons_list:
		I=H.get(_d)
		if I is _A:continue
		try:B=int(I)
		except(TypeError,ValueError):continue
		E=H.get(_B,'');J=E.lower()
		if J.endswith((_f,_g,_h,_i))or _RAISE_NAME_RE.search(E):C=B
		elif J.endswith((_j,_k,_l,_m))or _LOWER_NAME_RE.search(E):D=B
		A.append(B);K=_strip_engraving(E,area_name,O)
		if K:F[str(B)]=K
		L=H.get(_e)
		if L is not _A:
			try:
				M=int(L)
				if M!=B:G[str(M)]=B
			except(TypeError,ValueError):pass
	A=sorted(set(A));N=[A for A in A if A not in(C,D)];_LOGGER.debug('inline-buttons layout: %d total, configurable=%s raise=%s lower=%s names=%s leap_map=%s',len(A),N,C,D,F,G);return{_L:A,_M:N,_N:C,_O:D,_K:F,_n:G}
def _build_layout_from_bridge_buttons(candidates,area_name,device_name,has_raise_lower=True):
	J=has_raise_lower;D=[];A=_A;B=_A;H={};I=[]
	for F in candidates:
		K=F.get(_d)
		if K is _A:continue
		try:E=int(K)
		except(TypeError,ValueError):continue
		G=F.get('button_name')or F.get(_B,'');L=G.lower();O=F.get('button_led')is not _A
		if J:
			if L.endswith((_f,_g,_h,_i))or _RAISE_NAME_RE.search(G):A=E
			elif L.endswith((_j,_k,_l,_m))or _LOWER_NAME_RE.search(G):B=E
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
	D=sorted(set(D));N=[C for C in D if C not in(A,B)];_LOGGER.debug('bridge.buttons layout: %d total, configurable=%s raise=%s lower=%s names=%s',len(D),N,A,B,H);return{_L:D,_M:N,_N:A,_O:B,_K:H,_n:{}}
def _detect_button_layout(hass,serial,keypad_type,device_name='',area_name='',device_id='',device_data=_A):
	H=area_name;G=device_name;C=device_id;A=serial
	for E in _iter_lutron_bridges(hass):
		F=getattr(E,'button_devices',_A)or{}
		if F:
			I=[B for B in F.values()if A and str(B.get(_F,''))==A or C and str(B.get(_J,''))==C]
			if I:_LOGGER.debug('Strategy 1 (button_devices): %d entries for serial=%s device_id=%s',len(I),A,C);return _build_layout_from_button_devices(I,H,G)
		B=device_data
		if B is _A:
			try:O=E.get_devices()
			except Exception as P:_LOGGER.warning('bridge.get_devices() failed during layout detection: %s',P);continue
			for J in O.values():
				if A and str(J.get(_F,''))==A or C and str(J.get(_J,''))==C:B=J;break
		if B is _A:continue
		D=str(B.get(_J,''))or C;_LOGGER.debug('Device serial=%s on bridge %s — type=%r model=%r device_id=%s inline_buttons=%d button_devices_total=%d',A,type(E).__name__,B.get(_I),B.get(_o),D,len(B.get(_D,[])),len(F));K=B.get(_D,[])
		if K:_LOGGER.debug('Strategy 2 (inline buttons): %d buttons for serial=%s',len(K),A);return _build_layout_from_inline_buttons(K,H,G,B.get(_B,''))
		L=getattr(E,_D,_A)or{}
		if L:
			M=[B for B in L.values()if A and str(B.get(_F,''))==A or D and str(B.get('parent_device',''))==D]
			if M:_LOGGER.debug('Strategy 3 (bridge.buttons): %d buttons for serial=%s device_id=%s',len(M),A,D);from.const import KEYPAD_LAYOUTS as N,KEYPAD_GENERIC as Q;S,R=N.get(keypad_type,N[Q]);return _build_layout_from_bridge_buttons(M,H,G,has_raise_lower=R)
		_LOGGER.warning('Device serial=%s (type=%r model=%r device_id=%s) found on bridge but carries no button data (button_devices=%d, inline_buttons=0, bridge.buttons=%d). Full device info: %s',A,B.get(_I),B.get(_o),D,len(F),len(L),B);return{}
	_LOGGER.debug('Device serial=%s device_id=%s not found on any bridge; falling back to keypad-type static layout.',A,C);return{}
def _infer_lip_keypad_type(model):
	A=(model or'').lower()
	if _Y in A:return KEYPAD_PALLADIOM
	if _Z in A:return KEYPAD_SUNNATA
	if _a in A or'see touch'in A:return KEYPAD_SEETOUCH
	if'alisse'in A or'alise'in A:return KEYPAD_ALISEE
	if _b in A or'table top'in A:return KEYPAD_TABLETOP
	if _c in A:return KEYPAD_PICO
	return KEYPAD_GENERIC
async def _lip_xml_info(hass):
	S='Name';G=hass;import xml.etree.ElementTree as T;H=G.data.setdefault(DOMAIN,{}).setdefault('_lip_xml_info',{});M=G.config_entries.async_entries(_S)
	if not M:return{}
	B=M[0].data.get('host')
	if not B:return{}
	if B in H:return H[B]
	try:
		from homeassistant.helpers.aiohttp_client import async_get_clientsession as U;import aiohttp as V;W=U(G)
		async with W.get(f"http://{B}/DbXmlInfo.xml",timeout=V.ClientTimeout(total=15))as X:Y=await X.text()
		N=T.fromstring(Y);D=lambda tag:tag.split('}')[-1];O={B:A for A in N.iter()for B in A};I={}
		for A in N.iter():
			if D(A.tag)!='Device':continue
			if'KEYPAD'not in(A.get('DeviceType')or'').upper():continue
			P=A.get('IntegrationID')
			if not P:continue
			J=K='';C=O.get(A)
			while C is not _A:
				Q,E=D(C.tag),C.get(S)
				if Q=='DeviceGroup'and E and not K:K=E
				elif Q=='Area'and E and not J:J=E
				C=O.get(C)
			R={}
			for L in A.iter():
				if D(L.tag)!='Component':continue
				Z=L.get('ComponentNumber')
				for F in L:
					if D(F.tag)!='Button':continue
					try:a=int(Z)
					except(TypeError,ValueError):continue
					R[a]={_P:(F.get('Engraving')or'').strip(),_I:F.get('ButtonType')or'',_T:F.get('Direction')or''}
			I[str(P)]={_U:J,'group':K,_p:A.get(S)or'',_D:R}
		H[B]=I;return I
	except Exception:return{}
def _build_lip_name(nm,lip_id):
	E=lip_id;A=[]
	for B in(nm.get(_U,''),nm.get('group','')):
		B=(B or'').strip()
		if B and B.lower()not in(A.lower()for A in A):A.append(B)
	D=(nm.get(_p,'')or'').strip()
	if D and D.lower()not in(A.lower()for A in A):A.append(D)
	C=' '.join(A)
	if not C:return''
	if C.lower().rstrip().endswith(_H):return f"{C} {E}"
	return f"{C} Keypad {E}"
def _lip_button_info(hass):
	B={}
	try:
		F=hass.data.get(_S)or{}
		for G in F.values():
			C=getattr(G,_A5,_A)
			if C is _A:continue
			for H in getattr(C,'areas',[])or[]:
				for D in getattr(H,'keypads',[])or[]:
					E=str(getattr(D,'integration_id','')or'')
					if not E:continue
					I=B.setdefault(E,{})
					for A in getattr(D,_D,[])or[]:
						try:J=int(getattr(A,'component_number'))
						except(TypeError,ValueError):continue
						I[J]={_P:(getattr(A,_P,'')or'').strip(),_I:getattr(A,'button_type','')or'',_T:getattr(A,_T,'')or''}
	except Exception:return{}
	return B
async def _discover_lip_keypads(hass):
	F=hass;U=dr.async_get(F);V=er.async_get(F);W=_lip_button_info(F);X=await _lip_xml_info(F);P=[]
	for A in U.devices.values():
		B=next((str(A[1])for A in A.identifiers if A[0]==_S),_A)
		if B is _A:continue
		M=X.get(B,{});G=M.get(_D)or W.get(B,{})
		if G:C=sorted(G.keys())
		else:
			Q=set()
			for R in er.async_entries_for_device(V,A.id):
				if R.domain!='event':continue
				S=re.search('(\\d+)$',R.entity_id)
				if S:Q.add(int(S.group(1)))
			C=sorted(Q)
		if not C:continue
		K={};H=I=_A
		for D in C:
			N=G.get(D,{})if G else{};L=N.get(_T,'')
			if L==_q:H=D
			elif L==_r:I=D
			if L in(_q,_r):K[str(D)]=L
			elif N.get(_P):K[str(D)]=N[_P]
			else:K[str(D)]=f"Button {D}"
		if H is _A and I is _A and not G:I=18 if 18 in C else _A;H=19 if 19 in C else _A
		Y=[A for A in C if A not in(H,I)];O=A.model or'';J=(M.get(_U)or'').strip()
		if not J and A.area_id:
			T=ar.async_get(F).async_get_area(A.area_id)
			if T:J=T.name
		if A.name_by_user:E=A.name_by_user
		else:
			E=_build_lip_name(M,B)
			if not E:E=f"{J} keypad {B}"if J else A.name or f"keypad {B}"
		P.append({_G:f"lip_{B}",_B:E,_C:f"{E} ({O or _H}, {len(C)} buttons)",_V:{_B:E,'backend':_W,'lip_id':B,_J:A.id,CONF_DEVICE_SERIAL:f"lip_{B}",CONF_DEVICE_NAME:E,CONF_AREA_NAME:J,CONF_KEYPAD_TYPE:_infer_lip_keypad_type(O),_s:O,_L:C,_K:K,_M:Y,_N:H,_O:I}})
	return sorted(P,key=lambda k:k[_B])
def _has_rfwc5(hass):A=dr.async_get(hass);return any((A.model or'')==_t and any(A[0]=='zwave_js'for A in A.identifiers)for A in A.devices.values())
def _discover_rfwc5_keypads(hass):
	N='basic';M='sensor';G=hass;O=dr.async_get(G);P=er.async_get(G);H=[]
	for A in O.devices.values():
		if(A.model or'')!=_t:continue
		if not any(A[0]=='zwave_js'for A in A.identifiers):continue
		B=C=''
		for D in er.async_entries_for_device(P,A.id):
			E=D.entity_id;I=(D.original_name or'').lower()
			if not B and D.domain in(_E,M)and'indicator'in E+I:B=E
			if not C and D.domain==M and(N in E or I==N):C=E
		if not B or not C:continue
		J=f"rfwc5_{A.id}";K=''
		if A.area_id:
			L=ar.async_get(G).async_get_area(A.area_id)
			if L:K=L.name
		F=A.name_by_user or A.name or'RFWC5 Keypad';H.append({_G:J,_B:F,_C:f"{F} (Eaton RFWC5, 5 buttons)",_V:{_B:F,'backend':_X,_J:A.id,'indicator_entity':B,'basic_sensor':C,CONF_DEVICE_SERIAL:J,CONF_DEVICE_NAME:F,CONF_AREA_NAME:K,CONF_KEYPAD_TYPE:'generic',_s:_t,_L:[1,2,3,4,5],_K:{str(A):f"Button {A}"for A in range(1,6)},_M:[1,2,3,4,5],_N:_A,_O:_A}})
	return sorted(H,key=lambda k:k[_B])
class LutronKeypadsConfigFlow(config_entries.ConfigFlow,domain=DOMAIN):
	VERSION=1
	def __init__(A):A._discovered_keypads=[];A._selected_device=_A;A._detected_layout={}
	def _available_sources(B):
		A=[]
		if B.hass.config_entries.async_entries(_Q):A.append(_u)
		if B.hass.config_entries.async_entries(_S):A.append(_W)
		if _has_rfwc5(B.hass):A.append(_X)
		return A
	async def async_step_user(A,user_input=_A):
		B=A._available_sources()
		if not B:return A.async_abort(reason=_A6)
		if len(B)>1:return await A.async_step_source()
		return await getattr(A,f"async_step_{B[0]}")()
	async def async_step_source(A,user_input=_A):
		C=user_input;B='source';E={_u:'Caséta / RA2 Select (lutron_caseta)',_W:'Homeworks QS / RadioRA (lutron_lip)',_X:'Eaton RFWC5 (Z-Wave)'};D=A._available_sources()
		if C is not _A:return await getattr(A,f"async_step_{C[B]}")()
		return A.async_show_form(step_id=B,data_schema=vol.Schema({vol.Required(B,default=D[0]):vol.In({A:E[A]for A in D})}))
	async def async_step_rfwc5(A,user_input=_A):
		D=user_input;F=_discover_rfwc5_keypads(A.hass);G={A.unique_id or''for A in A.hass.config_entries.async_entries(DOMAIN)};B=[A for A in F if A[_G]not in G]
		if not B:return A.async_abort(reason=_v)
		E={}
		if D is not _A:
			H=D.get(_H);C=next((A for A in B if A[_G]==H),_A)
			if C is _A:E[_w]=_x
			else:await A.async_set_unique_id(C[_G]);A._abort_if_unique_id_configured();return A.async_create_entry(title=C[_B],data=C[_V])
		return A.async_show_form(step_id=_X,data_schema=vol.Schema({vol.Required(_H):vol.In({A[_G]:A[_C]for A in B})}),errors=E,description_placeholders={_y:str(len(B))})
	async def async_step_lip(A,user_input=_A):
		D=user_input;F=await _discover_lip_keypads(A.hass);G={A.unique_id or''for A in A.hass.config_entries.async_entries(DOMAIN)};B=[A for A in F if A[_G]not in G]
		if not B:return A.async_abort(reason=_v)
		E={}
		if D is not _A:
			H=D.get(_H);C=next((A for A in B if A[_G]==H),_A)
			if C is _A:E[_w]=_x
			else:await A.async_set_unique_id(C[_G]);A._abort_if_unique_id_configured();return A.async_create_entry(title=C[_B],data=C[_V])
		return A.async_show_form(step_id=_W,data_schema=vol.Schema({vol.Required(_H):vol.In({A[_G]:A[_C]for A in B})}),errors=E,description_placeholders={_y:str(len(B))})
	async def async_step_caseta(A,user_input=_A):
		F='device_serial';C=user_input;G=A.hass.config_entries.async_entries(_Q)
		if not G:return A.async_abort(reason=_A6)
		if not A._discovered_keypads:A._discovered_keypads=await A.hass.async_add_executor_job(_discover_keypads,A.hass)
		if not A._discovered_keypads:return await A.async_step_manual()
		H={A.unique_id or''for A in A.hass.config_entries.async_entries(DOMAIN)};B=[A for A in A._discovered_keypads if str(A.get(_F,''))not in H]
		if not B:return A.async_abort(reason=_v)
		I=_build_device_options(B);D={}
		if C is not _A:
			E=C.get(F,'');A._selected_device=next((A for A in B if str(A.get(_F,''))==E),_A)
			if A._selected_device is _A:D[_w]=_x
			else:await A.async_set_unique_id(E);A._abort_if_unique_id_configured();J=str(A._selected_device.get(_F,''));K=_infer_keypad_type(A._selected_device.get(_I,''));A._detected_layout=_detect_button_layout(A.hass,J,K,device_name=A._selected_device.get(_B,''),area_name=A._selected_device.get(_R,''),device_id=str(A._selected_device.get(_J,'')),device_data=A._selected_device);return await A.async_step_confirm()
		return A.async_show_form(step_id=_u,data_schema=vol.Schema({vol.Required(F):vol.In(I)}),errors=D,description_placeholders={_y:str(len(B))})
	async def async_step_confirm(B,user_input=_A):
		G=user_input;A=B._selected_device
		if A is _A:return await B.async_step_user()
		E=A.get(_I,'');F=_infer_keypad_type(E);C=A.get(_R,'');D=A.get(_B,'');H=str(A.get(_F,''));I=f"{C} — {D}"if C else D
		if G is not _A:J=G.get(_B,I).strip();return B.async_create_entry(title=J,data={_B:J,CONF_DEVICE_SERIAL:H,CONF_DEVICE_NAME:D,CONF_AREA_NAME:C,CONF_KEYPAD_TYPE:F,_z:E,_s:A.get(_o,''),_J:A.get(_J,''),**B._detected_layout})
		K=B._detected_layout.get(_L,[])
		if K:L=f"{len(K)} buttons detected from bridge"
		else:M=get_button_list(F);L=f"{len(M)} buttons (estimated from keypad type)"
		return B.async_show_form(step_id='confirm',data_schema=vol.Schema({vol.Required(_B,default=I):str}),description_placeholders={_U:C or'—',_p:D,'keypad_type':F,_F:H,_z:E,'button_count':L})
	async def async_step_manual(B,user_input=_A):
		A=user_input;D={}
		if A is not _A:
			C=A.get(CONF_DEVICE_SERIAL,'').strip()
			if not C:D[CONF_DEVICE_SERIAL]='serial_required'
			else:await B.async_set_unique_id(C);B._abort_if_unique_id_configured();E=A.get(_B,C).strip();return B.async_create_entry(title=E,data={_B:E,CONF_DEVICE_SERIAL:C,CONF_DEVICE_NAME:A.get(CONF_DEVICE_NAME,''),CONF_AREA_NAME:A.get(CONF_AREA_NAME,''),CONF_KEYPAD_TYPE:KEYPAD_GENERIC,_z:''})
		return B.async_show_form(step_id='manual',data_schema=vol.Schema({vol.Required(_B):str,vol.Required(CONF_DEVICE_SERIAL):str,vol.Optional(CONF_DEVICE_NAME,default=''):str,vol.Optional(CONF_AREA_NAME,default=''):str}),errors=D,description_placeholders={'note':'Auto-discovery failed — the Lutron bridge may not be reachable yet. Enter the serial manually: press any button on the keypad and check Developer Tools → Events → lutron_caseta_button_event.'})
	async def async_step_panel(A,user_input=_A):
		B=user_input
		if not B:return A.async_abort(reason='no_data')
		C=str(B.get(CONF_DEVICE_SERIAL,'')).strip()
		if not C:return A.async_abort(reason='no_serial')
		await A.async_set_unique_id(C);A._abort_if_unique_id_configured();D=str(B.pop(_B,C)).strip()or C;return A.async_create_entry(title=D,data=B)
	async def async_step_controller(A,user_input=_A):await A.async_set_unique_id(_A5);A._abort_if_unique_id_configured();return A.async_create_entry(title='Lutron Keypad Controller',data={'_controller':True})
	@staticmethod
	@callback
	def async_get_options_flow(config_entry):return LutronKeypadsOptionsFlow()
_ACTION_OPTIONS=[{_A0:A,_C:B}for(A,B)in ACTION_TYPE_LABELS.items()]
class LutronKeypadsOptionsFlow(config_entries.OptionsFlow):
	def __init__(A):A._buttons_config={}
	def _get_all_buttons(A):return get_button_layout(A.config_entry.data)
	def _get_configurable(A):return[A for A in A._get_all_buttons()if not A[_A1]and not A[_A2]]
	def _get_raise_lower_note(C):
		A=[]
		for B in C._get_all_buttons():
			if B[_A1]:A.append(f"Button {B[_E]} (Raise)")
			elif B[_A2]:A.append(f"Button {B[_E]} (Lower)")
		if not A:return''
		return f"{", ".join(A)} are fixed raise/lower buttons and cannot be reassigned."
	def _get_led_bindings_note(C):
		B=C.hass.data.get(DOMAIN,{}).get('entry_controllers',{}).get(C.config_entry.entry_id)
		if B is _A or not B._led_map:return''
		D=['\n\n**Auto-discovered LED bindings:**']
		for A in sorted(B._led_map):E=B._buttons.get(A,{});F=C.config_entry.data.get(_K,{});G=E.get(_C)or C._buttons_config.get(A,{}).get(_C)or F.get(str(A))or f"Button {A}";D.append(f"- {G} (button #{A}) → `{B._led_map[A]}`")
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
	async def async_step_init(A,user_input=_A):B=A.config_entry.entry_id;return A.async_show_menu(step_id='init',menu_options=[_D,'license'],description_placeholders={'panel_url':f"/lutron-keypads?entry={B}",_A3:A.config_entry.title})
	async def async_step_license(A,user_input=_A):
		C=user_input;B='license_key'
		if C is not _A:D=dict(A.config_entry.options);D[B]=C.get(B,'').strip();return A.async_create_entry(title='',data=D)
		E=await async_get_instance_id(A.hass);F=vol.Schema({vol.Optional(B,default=A.config_entry.options.get(B,'')):str});return A.async_show_form(step_id='license',data_schema=F,description_placeholders={'instance_id':E})
	async def async_step_buttons(A,user_input=_A):
		D=user_input
		if not A._buttons_config:
			I=A.config_entry.options.get(_D,{})
			for(J,K)in I.items():
				try:A._buttons_config[int(J)]=dict(K)
				except(ValueError,TypeError):pass
		E=A._get_configurable();L=A.config_entry.data.get(_B,'Keypad')
		if D is not _A:
			for C in E:
				B=C[_E];M=A._buttons_config.get(B,{});G=D.get(f"button_{B}_action_type",ACTION_NONE);A._buttons_config[B]={**M,_C:D.get(f"button_{B}_label",f"Button {B}"),CONF_ACTION_TYPE:G}
				if G not in ACTION_TYPES_NEEDING_ENTITY:A._buttons_config[B][CONF_ACTION_TARGET]=[];A._buttons_config[B][CONF_LED_ENTITY]='';A._buttons_config[B][_A4]=''
			for C in A._get_all_buttons():
				if C[_A1]:A._buttons_config[C[_E]]={_C:_q,CONF_ACTION_TYPE:ACTION_RAISE}
				elif C[_A2]:A._buttons_config[C[_E]]={_C:_r,CONF_ACTION_TYPE:ACTION_LOWER}
			N=any(A._buttons_config.get(B[_E],{}).get(CONF_ACTION_TYPE)in ACTION_TYPES_NEEDING_ENTITY for B in E)
			if N:return await A.async_step_entities()
			return A.async_create_entry(title='',data={**A.config_entry.options,_D:{str(A):B for(A,B)in A._buttons_config.items()}})
		O=A.config_entry.data.get(_K,{});F={}
		for C in E:B=C[_E];H=A._buttons_config.get(B,{});P=O.get(str(B),f"Button {B}");F[vol.Optional(f"button_{B}_label",default=H.get(_C)or P)]=selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT));F[vol.Required(f"button_{B}_action_type",default=H.get(CONF_ACTION_TYPE,ACTION_NONE))]=selector.SelectSelector(selector.SelectSelectorConfig(options=_ACTION_OPTIONS,mode=selector.SelectSelectorMode.DROPDOWN))
		return A.async_show_form(step_id=_D,data_schema=vol.Schema(F),description_placeholders={_A3:L,'raise_lower_note':A._get_raise_lower_note(),_A7:A._get_led_bindings_note()})
	async def async_step_entities(B,user_input=_A):
		K=False;C=user_input;M=B._get_configurable();I=[A for A in M if B._buttons_config.get(A[_E],{}).get(CONF_ACTION_TYPE)in ACTION_TYPES_NEEDING_ENTITY];N=B.config_entry.data.get(_B,'Keypad')
		if not I:return B.async_create_entry(title='',data={**B.config_entry.options,_D:{str(A):B for(A,B)in B._buttons_config.items()}})
		if C is not _A:
			for J in I:
				A=J[_E];D=B._buttons_config[A][CONF_ACTION_TYPE];G=D in MULTI_ENTITY_ACTIONS;H=C.get(f"button_{A}_entity",[]if G else'');B._buttons_config[A][CONF_ACTION_TARGET]=(H if isinstance(H,list)else B._normalize_target(H))if G else H;B._buttons_config[A][CONF_LED_INVERT]=bool(C.get(f"button_{A}_led_invert",K))
				if D==ACTION_ENTITY_TOGGLE:B._buttons_config[A][CONF_LED_MODE]=C.get(f"button_{A}_led_mode",LED_MODE_ROOM);B._buttons_config[A][CONF_TARGET_BRIGHTNESS]=int(C.get(f"button_{A}_target_brightness")or 0);B._buttons_config[A][CONF_TARGET_COLOR_TEMP]=int(C.get(f"button_{A}_target_color_temp")or 0)
				if D==ACTION_STATEFUL_SCENE:B._buttons_config[A][CONF_LED_ENTITY]=C.get(f"button_{A}_led",'');L=C.get(f"button_{A}_scene_group",'');B._buttons_config[A][_A4]=L.strip()if isinstance(L,str)else''
			return B.async_create_entry(title='',data={**B.config_entry.options,_D:{str(A):B for(A,B)in B._buttons_config.items()}})
		E={}
		for J in I:
			A=J[_E];F=B._buttons_config.get(A,{});D=F.get(CONF_ACTION_TYPE,ACTION_NONE);O=ACTION_TYPE_DOMAINS.get(D,[]);G=D in MULTI_ENTITY_ACTIONS;E[vol.Optional(f"button_{A}_entity",default=B._default_entity(F,G))]=selector.EntitySelector(selector.EntitySelectorConfig(domain=O,multiple=G))
			if D==ACTION_ENTITY_TOGGLE:E[vol.Optional(f"button_{A}_target_brightness",default=F.get(CONF_TARGET_BRIGHTNESS,0)or 0)]=selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=100,step=1,unit_of_measurement='%',mode='slider'));E[vol.Optional(f"button_{A}_target_color_temp",default=F.get(CONF_TARGET_COLOR_TEMP,0)or 0)]=selector.NumberSelector(selector.NumberSelectorConfig(min=0,max=10000,step=100,unit_of_measurement='K',mode='box'));E[vol.Optional(f"button_{A}_led_mode",default=F.get(CONF_LED_MODE,LED_MODE_ROOM))]=selector.SelectSelector(selector.SelectSelectorConfig(options=[{_A0:LED_MODE_ROOM,_C:'Room Mode — LED on when any entity is on'},{_A0:LED_MODE_SCENE,_C:'Scene Mode — LED on when all entities match target'}],mode=selector.SelectSelectorMode.DROPDOWN))
			if D==ACTION_STATEFUL_SCENE:E[vol.Optional(f"button_{A}_led",default=F.get(CONF_LED_ENTITY,''))]=selector.EntitySelector(selector.EntitySelectorConfig(domain=['switch'],multiple=K));E[vol.Optional(f"button_{A}_scene_group",default=F.get(_A4,''))]=selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT))
			E[vol.Optional(f"button_{A}_led_invert",default=F.get(CONF_LED_INVERT,K))]=selector.BooleanSelector()
		return B.async_show_form(step_id='entities',data_schema=vol.Schema(E),description_placeholders={_A3:N,_A7:B._get_led_bindings_note()})