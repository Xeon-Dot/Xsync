"""Tests for xsync.models."""

import pytest
from pydantic import ValidationError

from xsync.models import GlobalConfig, Mirror, MirrorType, SyncStatus, XsyncConfig


class TestMirror:
    def test_valid_rsync_mirror(self):
        m = Mirror(
            name="ubuntu",
            url="rsync://mirror.example.com/ubuntu",
            local_path="/srv/mirrors/ubuntu",
        )
        assert m.name == "ubuntu"
        assert m.mirror_type == MirrorType.RSYNC
        assert m.enabled is True
        assert m.last_status == SyncStatus.NEVER

    def test_valid_http_mirror(self):
        m = Mirror(
            name="debian",
            url="http://ftp.debian.org/debian",
            local_path="/srv/mirrors/debian",
            mirror_type=MirrorType.HTTP,
        )
        assert m.mirror_type == MirrorType.HTTP

    def test_invalid_name_special_chars(self):
        with pytest.raises(ValidationError):
            Mirror(
                name="bad name!",
                url="rsync://mirror.example.com/ubuntu",
                local_path="/srv/mirrors/ubuntu",
            )

    def test_invalid_url_no_scheme(self):
        with pytest.raises(ValidationError):
            Mirror(
                name="ubuntu",
                url="mirror.example.com/ubuntu",
                local_path="/srv/mirrors/ubuntu",
            )

    def test_bandwidth_limit(self):
        m = Mirror(
            name="centos",
            url="rsync://mirror.example.com/centos",
            local_path="/srv/mirrors/centos",
            bandwidth_limit="10m",
        )
        assert m.bandwidth_limit == "10m"

    def test_default_rsync_options(self):
        m = Mirror(
            name="arch",
            url="rsync://mirror.example.com/arch",
            local_path="/srv/mirrors/arch",
        )
        assert "-avz" in m.rsync_options
        assert "--delete" in m.rsync_options


class TestXsyncConfig:
    def test_default_config(self):
        cfg = XsyncConfig()
        assert cfg.version == 1
        assert isinstance(cfg.global_config, GlobalConfig)
        assert cfg.mirrors == {}

    def test_add_mirror(self):
        cfg = XsyncConfig()
        cfg.mirrors["ubuntu"] = Mirror(
            name="ubuntu",
            url="rsync://mirror.example.com/ubuntu",
            local_path="/srv/mirrors/ubuntu",
        )
        assert "ubuntu" in cfg.mirrors
