# Verdaccio npm offline registry configuration

## Offline versus online configuration

By default, ope-verdaccio starts in an offline-only configuration, so it gets all of its npm modules from local storage. To start in online mode (for example, if you want to modify the storage to include additional modules that are read from npm), set the environment variable CONFIGFILE=configOnline.yaml

A typical docker run command to start in offline mode is:
```sh
cd /ope/docker_build_files/ope-verdaccio
docker run -d --rm --name ope-verdaccio -p 4873:4873 --volume /ope/volumes/verdaccio:/verdaccio/storage -e "CONFIGFILE=configOnline.yaml" ope-verdaccio
```

## Helpful hints

### Saving the offline registry
```
cd /ope/volumes
tar -czf verdaccio.tgz verdaccio/*
```

## Extracting an offline registry file to the volume
```
cd /ope/volumes
rm -rf verdaccio
tar -zxf verdaccio.tgz verdaccio
chown root:101 verdaccio
chmod 775 verdaccio
```
