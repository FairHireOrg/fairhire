"""Deterministic resume parsing into one canonical, lossless model."""

from fairhire.resume.model import Contact, Entry, Resume, Section, SkillGroup
from fairhire.resume.parse import parse_resume_text
from fairhire.resume.render import render_text

__all__ = ["Contact", "Entry", "Resume", "Section", "SkillGroup", "parse_resume_text", "render_text"]
