from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

PLUGIN_DIR = Path(__file__).resolve().parent


try:
    from .schemas import setup_cli
    from .tools import execute_raw_args
except ImportError:
    def _load_local_module(module_name: str):
        module_path = PLUGIN_DIR / f"{module_name}.py"
        spec = spec_from_file_location(f"daedalus_{module_name}", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"unable to load {module_name} from {module_path}")
        module = module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    setup_cli = _load_local_module("schemas").setup_cli
    execute_raw_args = _load_local_module("tools").execute_raw_args


def register(ctx):
    ctx.register_command(
        "relay",
        execute_raw_args,
        description="Operate the Hermes Relay runtime from the current Hermes session.",
    )
    ctx.register_cli_command(
        name="relay",
        help="Operate the Hermes Relay runtime.",
        setup_fn=setup_cli,
        description="Hermes Relay project control surface.",
    )

    skill_md = PLUGIN_DIR / "skills" / "operator" / "SKILL.md"
    if skill_md.exists():
        ctx.register_skill("operator", skill_md, description="Operate the Hermes Relay plugin.")
