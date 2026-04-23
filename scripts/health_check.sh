#!/bin/bash
# Docker health check script
curl -f http://localhost:8000/health || exit 1
