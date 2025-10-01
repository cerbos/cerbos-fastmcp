source .env.store
cerbosctl hub store --client-id=$CERBOS_HUB_CLIENT_ID --client-secret=$CERBOS_HUB_CLIENT_SECRET --store-id=$CERBOS_HUB_STORE_ID replace-files policies/
