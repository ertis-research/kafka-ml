import { Component, OnInit } from '@angular/core';
import { ResultService } from '../services/result.service';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, ActivatedRoute } from '@angular/router';
import { IoTInference } from '../shared/iot-inference.model';
import { Location } from '@angular/common';
import { MLModel } from '../shared/ml.model';
import { ModelService } from '../services/model.service';
import { IoTDevice } from '../shared/iotdevice.model';
import { IoTDeviceService } from '../services/iot-devices.service';

@Component({
  selector: 'app-inference-iot-view',
  templateUrl: './inference-iot-view.component.html',
  styleUrls: ['./inference-iot-view.component.css'],
})
export class InferenceIoTViewComponent implements OnInit {
  resultID: number;
  inference = new IoTInference();
  valid: boolean = false;
  model: MLModel = new MLModel();
  distributed: Boolean = false;
  availableDevices: JSON[] = [];

  constructor(
    private resultService: ResultService,
    private modelService: ModelService,
    private iotDeviceService: IoTDeviceService,
    private snackbar: MatSnackBar,
    private route: ActivatedRoute,
    private router: Router,
    private location: Location
  ) {}

  ngOnInit(): void {
    if (this.route.snapshot.paramMap.has('id')) {
      this.resultID = Number(this.route.snapshot.paramMap.get('id'));
      this.modelService.getModelResultID(this.resultID).subscribe(
        (data) => {
          this.model = <MLModel>data;
          if (this.model.distributed && this.model.father != null) {
            this.distributed = true;
          } else {
            this.distributed = false;
          }
        }, //changed
        (err) => {
          this.valid = false;
          this.snackbar.open('Error model not found', '', {
            duration: 3000,
          });
        }
      );
      
      this.iotDeviceService.getIoTDevices().subscribe(
        (data) => {
          this.availableDevices = data
          
          // filter for devices where status is 'available'
          this.availableDevices = this.availableDevices.filter(
            (device) => device['status'] === 'connected'
          );
        },
        (err) => {
          this.valid = false;
          this.snackbar.open('Error fetching devices', '', {
            duration: 3000,
          });
        }
      );
    }
  }

  back() {
    this.location.back();
  }

  deployIoTInference(inference: IoTInference) {
    inference.model_result = this.resultID;
    this.resultService.deployIoTInference(this.resultID, inference).subscribe(
      (data: JSON[]) => {
        this.snackbar.open('Model deployed for inference', '', {
          duration: 3000,
        });
        this.router.navigateByUrl('/results');
      },
      (err) => {
        this.snackbar.open('Error deploying the model for inference', '', {
          duration: 3000,
        });
      }
    );
  }
}
