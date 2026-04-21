import importlib.util
from pathlib import Path


INSTALL_MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "install.py"


def load_install_module():
    spec = importlib.util.spec_from_file_location("hermes_relay_install", INSTALL_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_install_into_default_hermes_home_copies_plugin_tree(tmp_path):
    install = load_install_module()
    repo_root = Path(__file__).resolve().parents[1]
    hermes_home = tmp_path / ".hermes"

    result = install.install_plugin(repo_root=repo_root, hermes_home=hermes_home)

    plugin_dir = hermes_home / "plugins" / "hermes-relay"
    assert result == plugin_dir
    assert (plugin_dir / "plugin.yaml").exists()
    assert (plugin_dir / "runtime.py").exists()
    assert (plugin_dir / "alerts.py").exists()
    assert (plugin_dir / "skills" / "operator" / "SKILL.md").exists()


def test_install_into_explicit_destination_uses_given_path(tmp_path):
    install = load_install_module()
    repo_root = Path(__file__).resolve().parents[1]
    target = tmp_path / "custom-plugins" / "hermes-relay"

    result = install.install_plugin(repo_root=repo_root, destination=target)

    assert result == target
    assert (target / "plugin.yaml").exists()
    assert (target / "tools.py").exists()
