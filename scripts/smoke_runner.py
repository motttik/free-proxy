#!/usr/bin/env python3
"""
E2E Smoke Test (Test Wrapper)

Wrapper for fp.smoke module
"""

import asyncio
import sys

# Import from runtime module, not duplicate
from fp.smoke import smoke_test, print_report, main

if __name__ == "__main__":
    asyncio.run(main())
