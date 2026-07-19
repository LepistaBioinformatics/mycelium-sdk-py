## v0.2.0 (2026-07-19)

### Feat

- add compress_and_encode_profile_to_base64
- bring Profile to full parity with the gateway

### Fix

- rollback to the last changes in decoder

## v0.1.0a7 (2025-12-02)

### Fix

- decode from base64 before parse profile from zstandard

## v0.1.0a6 (2025-11-28)

### Feat

- turn zstandard optional dependency
- implements the decoding from header of the profile
- implements the decoding function for profile fetching

## v0.1.0a5 (2025-09-30)

### Fix

- include the filtration state on filter by permission

## v0.1.0a4 (2025-09-22)

### Feat

- do implements the profile extraction as optional and required dependency in fastapi context

## v0.1.0a3 (2025-09-22)

### Feat

- do implements the middleware to extract profile from header as optional
- do implements the on-account method to filter users by account
- do implements the first account filtering function
- do implements the with-roles method to profile
- implements the on-tenant method to profile to allow filtering by tenant

### Fix

- remove the is-admin flag from the profile model
- fix permissions filtering to be more elastic

## v0.1.0a2 (2025-09-22)

### Feat

- do implements the on-account method to filter users by account
- do implements the first account filtering function
- do implements the with-roles method to profile
- implements the on-tenant method to profile to allow filtering by tenant

### Fix

- fix permissions filtering to be more elastic

## v0.1.0a1 (2025-09-22)
