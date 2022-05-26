import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';
import { ModelViewComponent } from './model-view/model-view.component';
import { ModelListComponent } from './model-list/model-list.component';
import { ConfigurationListComponent } from './configuration-list/configuration-list.component';
import { ConfigurationViewComponent } from './configuration-view/configuration-view.component';
import { DeploymentListComponent } from './deployment-list/deployment-list.component';
import { DeploymentViewComponent } from './deployment-view/deployment-view.component';
import { ResultListComponent } from './result-list/result-list.component';
import {DatasourceListComponent} from './datasource-list/datasource-list.component'
import {InferenceViewComponent} from './inference-view/inference-view.component'
import {InferenceListComponent} from './inference-list/inference-list.component'
import {PlotViewComponent} from './plot-view/plot-view.component'
import {VisualizationComponent} from './visualization/visualization.component'

const routes: Routes = [
  {path: 'configuration-create', component: ConfigurationViewComponent},
  {path: 'configurations', component: ConfigurationListComponent},
  {path: 'configuration/:id', component: ConfigurationViewComponent},
  {path: 'datasources', component: DatasourceListComponent},
  {path: 'deploy/:id', component: DeploymentViewComponent},
  {path: 'inferences', component: InferenceListComponent},
  {path: 'model-create', component: ModelViewComponent},
  {path: 'deployments', component: DeploymentListComponent},
  {path: 'deployments/:id', component: DeploymentListComponent},
  {path: 'models', component: ModelListComponent},
  {path: 'model/:id', component: ModelViewComponent},
  {path: 'results', component: ResultListComponent},
  {path: 'results/:id', component: ResultListComponent},
  {path: 'results/inference/:id', component: InferenceViewComponent},
  {path: 'results/chart/:id', component: PlotViewComponent},
  {path: 'visualization', component: VisualizationComponent}
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule]
})
export class AppRoutingModule { }
