# Front-end

This project provides the front-end of Kafka-ML and was generated with [Angular CLI](https://github.com/angular/angular-cli) version 9.1.0-next.2.

A brief introduction of most important files and folders:
- Folder `src/app/shared/*`  objects to represent front-end instances in Angular. 
- Folder `src/app/services/*` services which communicate with the back-end. 
- Folder `src/app/*` the rest of Angular components to implement the forms used in Kafka-ML (configuration, deployments, etc.). Each form is usually represented by component whose name ends with `-list` for visualization (e.g., `model-list`), and ending with `-view` for creation and update (e.g, `model-view`).
- File `src/app/app-routing.module.ts` match the front-end API to the Angular components defined.
- Folder `src/app/environments` environments used to connect with the back-end. Default `environment.ts` file, and environment.prod.ts will be used when running the front-end in production in Kubernetes.

## Development server
Run `npm install` to install the dependencies of the front-end. Just once, npm is required.

Run `ng serve` to execute the development server. Navigate to `http://localhost:4200/`. The app will automatically reload if you change any of the source files.

## Code scaffolding

Run `ng generate component component-name` to generate a new component. You can also use `ng generate directive|pipe|service|class|guard|interface|enum|module`.

## Build for deploying in Kubernetes

Run `ng build` to build the project. The build artifacts will be stored in the `dist/` directory. Use the `--prod` flag for a production build. This is required when generating the front-end image to be deployed in Kubernetes.

## Running unit tests

Run `ng test` to execute the unit tests via [Karma](https://karma-runner.github.io). Not provided yet.

## Running end-to-end tests

Run `ng e2e` to execute the end-to-end tests via [Protractor](http://www.protractortest.org/).  Not provided yet.

## Further help

To get more help on the Angular CLI use `ng help` or go check out the [Angular CLI README](https://github.com/angular/angular-cli/blob/master/README.md).

## Environments vars when deploying the back-end in Kubernetes
- **BACKEND_URL**: URL and port for the back-end connection (e.g, http://localhost:8000)

