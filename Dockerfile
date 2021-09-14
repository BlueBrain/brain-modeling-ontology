FROM python:2.7 AS generator

# define working directory
WORKDIR /app

ARG GITLAB_DEPLOY_TOKEN
ARG GITLAB_DEPLOY_PASSWORD

# Install requirements
RUN pip install pyld==1.0.4 ontospy==1.9.1 rdflib==4.2.2 pygments==2.1.3
RUN pip install git+https://$GITLAB_DEPLOY_TOKEN:$GITLAB_DEPLOY_PASSWORD@bbpgitlab.epfl.ch/dke/apps/ontodocs.git

# Copy rest of files
COPY . .
# Create directory to host visualization files
RUN mkdir /app/visualization
# Generate ontologies documentation
RUN ontodocs ./ontologies/bbp --theme lumen --outputpath /app/visualization --title "Brain Modeling Ontology"

FROM nginx:latest

WORKDIR /usr/share/nginx/html
# Copy generated files to nginx default html directory
COPY --from=generator /app/visualization /usr/share/nginx/html
# Copy nginx custom configuration to default directory
COPY nginx.conf /etc/nginx/nginx.conf
# Expose port
EXPOSE 8080
# Run nginx server
CMD ["nginx", "-g", "daemon off;"]