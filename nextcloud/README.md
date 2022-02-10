## Nextcloud

### Setup

0. Create `.env` file with `DB_ROOT_PASSWD` variable, e.g.:

```
DB_ROOT_PASSWD="xxxxxxxxxxxxxx"
```

1. Create data volumes:

```
docker volume create nextcloud
docker volume create nextcloud_postgres
```

2. Run `docker-compose up -d`
