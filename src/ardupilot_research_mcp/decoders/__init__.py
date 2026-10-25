"""Deterministic protocol decoders. Pure stdlib, no I/O, no network."""

from .crsf import crc8_dvb_s2, parse_frames, unpack_channels
from .ihex import parse_record as parse_ihex_record, summarize as summarize_ihex

__all__ = ["crc8_dvb_s2", "parse_frames", "unpack_channels", "parse_ihex_record", "summarize_ihex"]
