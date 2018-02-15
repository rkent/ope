# Verdaccio npm offline registry configuration

## Offline versus online configuration

By default, ope-verdaccio starts in an offline-only configuration, so it gets all of its npm modules from local storage. To start in online mode (for example, if you want to modify the storage to include additional modules that are read from npm), set the environment variable CONFIGFILE=configOnline.yaml

## Helpful hints

### Saving the offline registry
```
cd /ope/volumes
tar -cf verdaccio.tgz verdaccio/*
```

## Extracting an offline registry file to the volume
```
cd /ope/volumes
rm -rf verdaccio
tar -zxf verdaccio.tgz verdaccio
chown root:101 verdaccio
chmod verdaccio 775
```
