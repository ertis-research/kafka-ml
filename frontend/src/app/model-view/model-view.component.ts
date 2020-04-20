import { Component, OnInit } from '@angular/core';
import {MatSnackBar} from '@angular/material/snack-bar';
import { Router, ActivatedRoute } from '@angular/router';
import { ModelService } from '../services/model.service';
import {MLModel} from "../shared/ml.model";
import {Location} from '@angular/common';

@Component({
  selector: 'app-model-view',
  templateUrl: './model-view.component.html',
  styleUrls: ['./model-view.component.css']
})
export class ModelViewComponent implements OnInit {
  modelId: number = undefined;
  model : MLModel = new MLModel();
  create: Boolean = true;
  valid: Boolean = true;
  constructor(private modelService: ModelService,
              private snackbar: MatSnackBar,
              private router: Router,
              private route: ActivatedRoute,
              private _location: Location) { }

  ngOnInit(): void {
    // Get the ID in case of a edit request
    if (this.route.snapshot.paramMap.has('id')){
        this.modelId = Number(this.route.snapshot.paramMap.get('id'));
        this.create=false;
    }
    if (this.modelId!= undefined){
        this.modelService.getModel(this.modelId).subscribe(
          (data) => {
            this.model=<MLModel> data;
          },  //changed
          (err)=>{
            this.valid = false;
            this.snackbar.open('Error model not found', '', {
              duration: 3000
            });
          }
      );
    }
  }
  back() {
    this._location.back();
  }

  onSubmit(model: JSON) {
    if (this.modelId!= undefined){
      this.modelService.editModel(this.modelId, model).subscribe(
        (data) => {},  //changed
        (err)=>{
          this.snackbar.open('Error updating the model: '+err.error, '', {
            duration: 3000
          });
        },
        ()=>{
          this.router.navigateByUrl('/models');
          this.snackbar.open('Model updated ', '', {
          duration: 3000
        });}
     );
    }
    else{
          this.modelService.createModel(model).subscribe(
            (data) => {},  //changed
            (err)=>{
              this.snackbar.open('Error creating the model: '+err.error, '', {
                duration: 3000
              });
            },
            ()=>{
              this.router.navigateByUrl('/models');
              this.snackbar.open('Model created ', '', {
              duration: 3000
            });}
         );
      }
  }

}
