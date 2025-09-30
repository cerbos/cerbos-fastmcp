source .env.pdp
cerbos server --set=audit.enabled=true --set=audit.backend=hub --set=audit.hub.storagePath=/tmp
