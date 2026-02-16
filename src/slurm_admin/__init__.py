"""
Slurm Lifecycle Monitor (SLM)
A low-coupling monitoring solution for Slurm job lifecycle management
"""

__version__ = "0.1.0"

from .database import DatabaseConfig, SlurmDatabase, get_database, close_database

__all__ = [
    "DatabaseConfig",
    "SlurmDatabase",
    "get_database",
    "close_database",
]
