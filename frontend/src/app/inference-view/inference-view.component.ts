import { Component, OnInit } from '@angular/core';
import { ResultService } from '../services/result.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import {Router, ActivatedRoute } from '@angular/router';
import {Inference} from '../shared/inference.model'
import {Location} from '@angular/common';
import { MLModel } from '../shared/ml.model';
import { ModelService } from '../services/model.service';

@Component({
  selector: 'app-inference-view',
  templateUrl: './inference-view.component.html',
  styleUrls: ['./inference-view.component.css']
})
export class InferenceViewComponent implements OnInit {

  resultID: number;
  inference = new Inference();
  valid: boolean = false;
  model: MLModel = new MLModel();
  distributed: Boolean = false;
  
  constructor(private resultService: ResultService,
  private modelService: ModelService,
  private snackbar: MatSnackBar,
  private route: ActivatedRoute,
  private router: Router,
  private location: Location) { }

  ngOnInit(): void {
    if (this.route.snapshot.paramMap.has('id')) {
      this.resultID = Number(this.route.snapshot.paramMap.get('id'));
      this.resultService.getInferenceInfo(this.resultID).subscribe((data: JSON[]) => {
        if (data['input_format'] != ''){
          this.inference.input_format = data['input_format'];
          this.inference.input_config = data['input_config'];
          this.snackbar.open('Input format and configuration found from another dataset/inference', '', {
            duration: 3000
          });
        }
        this.valid = true;
      },
      (err) => {
        this.snackbar.open('The training result does not exist', '', {
          duration: 3000
        });
      });
      this.modelService.getModelResultID(this.resultID).subscribe(
        (data) => {
          this.model=<MLModel> data;
          if(this.model.distributed && this.model.father != null) {
            this.distributed = true;
          } else {
            this.distributed = false;
          }
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
    this.location.back();
  }

  deployInference(inference: Inference) {
    inference.model_result = this.resultID;
    this.resultService.deployInference(this.resultID, inference).subscribe((data: JSON[]) => {
      this.snackbar.open('Model deployed for inference', '', {
        duration: 3000
      });
      this.router.navigateByUrl('/inferences');
    },
    (err) => {
      this.snackbar.open('Error deploying the model for inference', '', {
        duration: 3000
      });
    });
  }
}