The (excellent) upstream Docker image that contains all the GNAF data is
huge (32GB). In order to consume less resources, we can create a cut-down
version of this, with just the single table that this tool actually uses,
as well as a DB index already created.

~~In order to do this, we use the upstream Docker container as a base image, 
then run an export command to extract just the data we need into a CSV.~~

Using the upstream image works, but uses too much space to run in Github
Actions.  As an alternative, we download the DB dump file, the restore
just the table we are interested in.  This creates a 9.45GB image.
To make the image even smaller, we export just the columns want.

Then we rebuild the Postgresql server, basically the same as the upstream
image, and create a single table with the exported data.

The new Docker image is 3.73GB compared to the original 32GB.

```
❯ docker images
REPOSITORY           TAG       IMAGE ID       CREATED          SIZE
mydb                 latest    84af660a3493   39 seconds ago   3.73GB
minus34/gnafloader   latest    d2c552c72a0a   10 days ago      32GB
```

# References

- Hugh Saalmans Docker image containing all the GNAF data [gnaf-loader](https://github.com/minus34/gnaf-loader)

- [Dockerfile](https://github.com/minus34/gnaf-loader/blob/master/docker/Dockerfile) from that image