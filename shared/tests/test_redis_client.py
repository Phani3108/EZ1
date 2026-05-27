"""Tests for the sentinel-aware redis client factory (INFRA-006 / Phase 5)."""
from unittest.mock import MagicMock, patch

import pytest

from eduzim_shared.redis_client import from_url


class TestPlainRedisUrl:
    """`redis://` and `rediss://` go through redis.from_url unchanged."""

    @patch("redis.from_url")
    def test_redis_scheme_passes_through(self, mock_from_url):
        mock_from_url.return_value = MagicMock(name="redis-client")
        client = from_url("redis://localhost:6379/0")
        mock_from_url.assert_called_once()
        # First positional arg is the URL.
        assert mock_from_url.call_args[0][0] == "redis://localhost:6379/0"

    @patch("redis.from_url")
    def test_rediss_scheme_passes_through(self, mock_from_url):
        mock_from_url.return_value = MagicMock()
        from_url("rediss://prod:6379/2")
        assert mock_from_url.call_args[0][0] == "rediss://prod:6379/2"

    @patch("redis.from_url")
    def test_options_forwarded(self, mock_from_url):
        mock_from_url.return_value = MagicMock()
        from_url("redis://x/0", decode_responses=False, socket_timeout=10.0)
        kwargs = mock_from_url.call_args[1]
        assert kwargs["decode_responses"] is False
        assert kwargs["socket_timeout"] == 10.0


class TestSentinelUrl:
    """`redis+sentinel://` parses into Sentinel().master_for(...)."""

    def _patch_sentinel(self):
        """Patch redis.sentinel.Sentinel and return the mock + the master_for return value."""
        mock_sentinel_cls = MagicMock(name="Sentinel")
        mock_sentinel_instance = MagicMock(name="sentinel-instance")
        mock_master = MagicMock(name="master-client")
        mock_sentinel_cls.return_value = mock_sentinel_instance
        mock_sentinel_instance.master_for.return_value = mock_master
        return mock_sentinel_cls, mock_sentinel_instance, mock_master

    def test_three_sentinel_hosts_parsed(self):
        mock_cls, mock_instance, mock_master = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url(
                "redis+sentinel://:pw@s0:26379,s1:26379,s2:26379/3?master=mymaster"
            )
        sentinels_arg = mock_cls.call_args[0][0]
        assert sentinels_arg == [("s0", 26379), ("s1", 26379), ("s2", 26379)]

    def test_password_extracted_from_url(self):
        mock_cls, _, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url(
                "redis+sentinel://:secret@s0:26379/0?master=mymaster"
            )
        assert mock_cls.call_args[1]["password"] == "secret"

    def test_master_name_extracted(self):
        mock_cls, mock_instance, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url(
                "redis+sentinel://s0:26379/0?master=eduzim-master"
            )
        master_name = mock_instance.master_for.call_args[0][0]
        assert master_name == "eduzim-master"

    def test_master_defaults_to_mymaster(self):
        mock_cls, mock_instance, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url("redis+sentinel://s0:26379/0")
        assert mock_instance.master_for.call_args[0][0] == "mymaster"

    def test_db_index_parsed(self):
        mock_cls, mock_instance, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url("redis+sentinel://s0:26379/7?master=mymaster")
        assert mock_instance.master_for.call_args[1]["db"] == 7

    def test_empty_db_defaults_to_zero(self):
        mock_cls, mock_instance, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url("redis+sentinel://s0:26379/?master=mymaster")
        assert mock_instance.master_for.call_args[1]["db"] == 0

    def test_default_sentinel_port_when_omitted(self):
        mock_cls, _, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            from_url("redis+sentinel://s0,s1/0?master=mymaster")
        sentinels_arg = mock_cls.call_args[0][0]
        assert sentinels_arg == [("s0", 26379), ("s1", 26379)]

    def test_no_sentinels_raises(self):
        with pytest.raises(ValueError, match="no sentinel hosts"):
            from_url("redis+sentinel:///0?master=mymaster")

    def test_bad_db_index_raises(self):
        mock_cls, _, _ = self._patch_sentinel()
        with patch("redis.sentinel.Sentinel", mock_cls):
            with pytest.raises(ValueError, match="non-int db"):
                from_url("redis+sentinel://s0:26379/abc?master=mymaster")
