import { Component, OnInit } from '@angular/core';
import {MatSnackBar} from '@angular/material/snack-bar';
import { Router, ActivatedRoute } from '@angular/router';
import { ModelService } from '../services/model.service';
import {MLModel} from "../shared/ml.model";
import {Location} from '@angular/common';

export function determineId(model: any): string {
  var res = model;
  if (model != null && typeof model != 'number') {
     res = model.id;
  }
  return res;
}

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
  distributedModels : JSON[];
  showFather: Boolean = false;
  framework: string = "";
  placeholder: string = "";
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
            this.showFather = this.model.distributed;
            this.framework = this.model.framework;
          },  //changed
          (err)=>{
            this.valid = false;
            this.snackbar.open('Error model not found', '', {
              duration: 3000
            });
          }
      );
    }
    this.modelService.getDistributedModels().subscribe(
      (data) => {
        this.distributedModels= data;
      }, 
      (err)=>{
        this.snackbar.open('Error connecting with the server', '', {
          duration: 3000
        });
      }
    );
  }
  
  back() {
    this._location.back();
  }

  tfClick(){
    this.framework = "tf";
  }

  pthClick(){
    this.showFather = false;
    this.framework = "pth"
  }

  getPlaceholder(): string {
    var txt = ""
    if (this.framework == "tf"){
      txt =`model = tf.keras.models.Sequential([
        tf.keras.layers.Flatten(input_shape=(28, 28)), 
        tf.keras.layers.Dense(128, activation='relu'),
        tf.keras.layers.Dense(10, activation='softmax')
      ])
model.compile(optimizer=tf.keras.optimizers.Adam(0.001),
      loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True), 
      metrics=[tf.keras.metrics.SparseCategoricalAccuracy()])
    `;
    }else if(this.framework == "pth"){
      txt = `class NeuralNetwork(nn.Module):
      def __init__(self):
          super(NeuralNetwork, self).__init__()
          self.flatten = nn.Flatten()
          self.linear_relu_stack = nn.Sequential(
              nn.Linear(28*28, 128),
              nn.ReLU(),
              nn.Linear(128, 10),
              nn.Softmax()
          )

      def forward(self, x):
          x = self.flatten(x)
          logits = self.linear_relu_stack(x)
          return logits

      def loss_fn(self):
          return nn.CrossEntropyLoss()

      def optimizer(self):
          return torch.optim.Adam(model.parameters(), lr=1e-3)

      def metrics(self):
          val_metrics = {
              "accuracy": Accuracy(),
              "loss": Loss(self.loss_fn())
           }
          return val_metrics

model = NeuralNetwork()
`;
    }
    return txt;
  }

  compareModels(o1: any, o2: any): boolean {
    const a1 = determineId(o1);
    const a2 = determineId(o2);
    return a1 === a2;
  }

  controlFather(e: any) {
    if (e.checked) {
      this.showFather = true;
    } else {
      this.showFather = false;
    }
  }

  onSubmit(model: JSON) {
    if (this.modelId!= undefined){
      if (isNaN(model['father'])) {
        if (model['father'] != undefined) {
          model['father'] = model['father']['id'];
        }
      }
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