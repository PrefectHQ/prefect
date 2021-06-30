This section of our quick-start guide is aimed at Prefect Server users.  If you want to set up Prefect Cloud, go to [Set Up Prefect Cloud](). 

Prefect Server is included with the Prefect python package you installed earlier in the quick start guide.  

## Set backend 
Your first step is to make sure your backend is set to use Prefect Server by running 

  ```bash
$ prefect backend server
```
Note that you can change backends at any time by rerunning the `prefect backend ...` command.

## Start server

You can start server by running 

```bash
$ prefect server start
```

Ensure that you have docker installed on whichever machine you are running server. 

You should see a welcome message and be able to navigate to the server UI at http://localhost:8080

