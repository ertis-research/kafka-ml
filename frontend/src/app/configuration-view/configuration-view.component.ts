import { Component, OnInit } from '@angular/core';
import {MatSnackBar} from '@angular/material/snack-bar';
import { Router, ActivatedRoute } from '@angular/router';
import { ModelService } from '../services/model.service';
import { ConfigurationService } from '../services/configuration.service';
import {MLModel} from "../shared/ml.model";
import {Configuration} from "../shared/configuration.model";
import {Location} from '@angular/common';

export function determineId(model: any): string {
  var res = model;
  if (model != null && typeof model != 'number') {
     res = model.id;
  }
  return res;
}

@Component({
  selector: 'app-configuration-view',
  templateUrl: './configuration-view.component.html',
  styleUrls: ['./configuration-view.component.css']
})
export class ConfigurationViewComponent implements OnInit {

  configurationId: number = undefined;
  models : JSON[];
  create: Boolean = true;
  configuration: Configuration =new Configuration();
  valid: Boolean =true;
  constructor(private modelService: ModelService,
              private configurationService: ConfigurationService,
              private snackbar: MatSnackBar,
              private router: Router,
              private route: ActivatedRoute,
              private location: Location) { }

  ngOnInit(): void {
    this.modelService.getFatherModels().subscribe(
          (data) => {
            this.models= data;
          }, 
          (err)=>{
            this.snackbar.open('Error connecting with the server', '', {
              duration: 3000
            });
          }
      );

      if (this.route.snapshot.paramMap.has('id')){
        this.configurationId = Number(this.route.snapshot.paramMap.get('id'));
        this.create=false;
    }
    if (this.configurationId!= undefined){
        this.configurationService.getConfiguration(this.configurationId).subscribe(
          (data) => {
            this.configuration= <Configuration> data;
          },  //changed
          (err)=>{
            this.valid = false;
            this.snackbar.open('Error configuration not found', '', {
              duration: 3000
            });
          }
      );
    }
  }

  compareModels(o1: any, o2: any): boolean {
    const a1 = determineId(o1);
    const a2 = determineId(o2);
    return a1 === a2;
  }

  back() {
    this.location.back();
  }

  onSubmit(configuration: JSON) {
  

    if (this.configurationId!= undefined){
      var ml_models=[]
      // to refresh select when there are no changes
      for (var id in configuration['ml_models']){
          ml_models.push(determineId(configuration['ml_models'][id]))
      }
      configuration['ml_models']=ml_models;
      this.configurationService.editConfiguration(this.configurationId, configuration).subscribe(
        (data) => {},  //changed
        (err)=>{
          this.snackbar.open('Error updating the configuration: '+err.error, '', {
            duration: 3000
          });
        },
        ()=>{
          this.router.navigateByUrl('/configurations');
          this.snackbar.open('Configuration updated ', '', {
          duration: 3000
        });}
     );
    }
    else{
          this.configurationService.createConfiguration(configuration).subscribe(
            (data) => {},  //changed
            (err)=>{
              this.snackbar.open('Error creating the configuration: '+err.error, '', {
                duration: 3000
              });
            },
            ()=>{
              this.router.navigateByUrl('/configurations');
              this.snackbar.open('Configuration created ', '', {
              duration: 3000
            });}
         );
      }
  }

}
