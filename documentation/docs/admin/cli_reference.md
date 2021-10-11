# Command Line Reference

## Initialization

```bash
# initialize the ACE system
# this will output export commands to load environment variables
dc run --rm ace acecli initialize | sed -ne '/^# START EXPORT/,/^# STOP EXPORT/ p' | tr -d '\r' > .ace-env

# load the generated environment variables
source .ace-env
```

## Starting ACE

```bash
docker-compose up -d
```

## Api Key Management

```bash
# create a new api key
acecli api-key create *name*

# delete an api key by name
acecli api-key delete name

# list all available api keys
acecli api-key list
```
