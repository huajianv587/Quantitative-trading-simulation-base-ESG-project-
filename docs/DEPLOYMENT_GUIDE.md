
# Deployment Guide

Use FastAPI for the control plane, Supabase for structured metadata, and Cloudflare R2 for artifacts when available.
If `R2_*` is not configured, the runtime now falls back to Supabase Storage first and only then to local disk.
