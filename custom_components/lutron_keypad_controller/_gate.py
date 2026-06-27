import importlib.util as _u,pathlib as _pl,platform as _p,sys as _s
_name=__name__.rsplit('.',1)[-1]
_root=_pl.Path(__file__).parent/'_native'
_so=_root/_p.machine()/f"{_name}.abi3.so"
if not _so.exists():_have=', '.join(p.name for p in _root.iterdir())if _root.exists()else'none';raise ImportError(f"Buttons Machine: no native build of {_name!r} for CPU arch {_p.machine()!r} (have: {_have}).")
_spec=_u.spec_from_file_location(__name__,_so)
_mod=_u.module_from_spec(_spec)
_s.modules[__name__]=_mod
_spec.loader.exec_module(_mod)
globals().update({k:v for(k,v)in vars(_mod).items()if not k.startswith('__')})