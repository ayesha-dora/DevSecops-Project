# Notes for devsecops-app

This chart deploys the sample DevSecOps application.

To install:
  helm install devsecops-app ./helm/devsecops-app --namespace default --create-namespace

To test rendering without installing:
  helm template devsecops-app ./helm/devsecops-app

To override values, use --set or provide a values file:
  helm install devsecops-app ./helm/devsecops-app --set image.tag=dev
