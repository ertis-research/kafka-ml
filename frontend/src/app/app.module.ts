import { BrowserModule } from '@angular/platform-browser';
import { NgModule } from '@angular/core';
import { HttpClientModule } from  '@angular/common/http';
import { BrowserAnimationsModule } from '@angular/platform-browser/animations';
import { FormsModule, ReactiveFormsModule } from '@angular/forms';

import { MaxCharPipe } from './shared/max-char.pipe';
import { AppRoutingModule } from './app-routing.module';
import { AppComponent } from './app.component';
import { ModelViewComponent } from './model-view/model-view.component';
import { ModelListComponent } from './model-list/model-list.component';
import { HeaderComponent } from './layout/header/header.component'; 


import {MatSidenavModule} from '@angular/material/sidenav';
import { MatToolbarModule} from '@angular/material/toolbar'; 
import { MatIconModule } from '@angular/material/icon';
import { MatListModule } from '@angular/material/list';
import { MatSliderModule } from '@angular/material/slider';
import {MatButtonModule} from '@angular/material/button'; 
import {MatCheckboxModule} from '@angular/material/checkbox';
import {MatTableModule} from '@angular/material/table';
import {MatFormFieldModule} from '@angular/material/form-field';
import {MatInputModule} from '@angular/material/input';
import {MatSelectModule} from '@angular/material/select';
import {MatSlideToggleModule} from '@angular/material/slide-toggle';
import {MatDialogModule, MatDialogRef, MAT_DIALOG_DATA} from '@angular/material/dialog';
import {MatRadioModule} from '@angular/material/radio';
import {MatSnackBarModule} from '@angular/material/snack-bar';
import {MatProgressSpinnerModule} from '@angular/material/progress-spinner'; 
import {MatCardModule} from '@angular/material/card';
import {MatPaginatorModule} from '@angular/material/paginator';
import { ConfirmDialogComponent } from './confirm-dialog/confirm-dialog.component';
import { ConfigurationListComponent } from './configuration-list/configuration-list.component';
import { MatGridListModule } from '@angular/material/grid-list';
import { MatMenuModule } from '@angular/material/menu';
import { LayoutModule } from '@angular/cdk/layout';
import { MatSortModule } from '@angular/material/sort';
import { SidenavListComponent } from './layout/sidenav-list/sidenav-list.component';
import { ConfigurationViewComponent } from './configuration-view/configuration-view.component';
import { DeploymentListComponent } from './deployment-list/deployment-list.component';
import { DeploymentViewComponent } from './deployment-view/deployment-view.component';
import { ResultListComponent } from './result-list/result-list.component';
import { DataFilterPipe } from './shared/filter';
import { DatasourceListComponent } from './datasource-list/datasource-list.component';
import { DatasourceDialogComponent } from './datasource-dialog/datasource-dialog.component';
import { InferenceViewComponent } from './inference-view/inference-view.component';
import { InferenceListComponent } from './inference-list/inference-list.component';
import { PlotViewComponent } from './plot-view/plot-view.component';
import { NgxChartsModule } from '@swimlane/ngx-charts';
import { VisualizationComponent } from './visualization/visualization.component';

@NgModule({
  declarations: [
    AppComponent,
    ModelViewComponent,
    ModelListComponent,
    HeaderComponent,
    MaxCharPipe,
    ConfirmDialogComponent,
    ConfigurationListComponent,
    SidenavListComponent,
    ConfigurationViewComponent,
    DeploymentListComponent,
    DeploymentViewComponent,
    ResultListComponent,
    DataFilterPipe,
    DatasourceListComponent,
    DatasourceDialogComponent,
    InferenceViewComponent,
    InferenceListComponent,
    PlotViewComponent,
    VisualizationComponent,

  ],
  imports: [
    BrowserModule,
    AppRoutingModule,
    HttpClientModule, // included HTTP client
    MatButtonModule,
    BrowserAnimationsModule,
    MatSliderModule,
    MatToolbarModule,
    MatIconModule,
    MatListModule,
    MatSidenavModule,
    MatCardModule,
    MatProgressSpinnerModule,
    MatCheckboxModule,
    MatTableModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    MatDialogModule,
    MatRadioModule,
    MatSnackBarModule,
    FormsModule, 
    ReactiveFormsModule,
    MatPaginatorModule,
    MatGridListModule,
    MatMenuModule,
    LayoutModule,
    MatSortModule,
    NgxChartsModule,
  ],
  providers: [{
    provide: MatDialogRef,
    useValue: {}
  },
  { provide: MAT_DIALOG_DATA, useValue: [] },
  DatasourceDialogComponent],
  bootstrap: [AppComponent],
})
export class AppModule { }

