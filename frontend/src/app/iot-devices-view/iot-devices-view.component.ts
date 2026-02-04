import { Component, OnInit } from '@angular/core';
import { MatSnackBar } from '@angular/material/snack-bar';
import { Router, ActivatedRoute } from '@angular/router';
import { Location } from '@angular/common';

import { IoTDeviceService } from '../services/iot-devices.service';
import { IoTDevice } from '../shared/iotdevice.model';

export function determineId(model: any): string {
  var res = model;
  if (model != null && typeof model != 'number') {
    res = model.id;
  }
  return res;
}

@Component({
  selector: 'app-iot-devices-view',
  templateUrl: './iot-devices-view.component.html',
  styleUrls: ['./iot-devices-view.component.css'],
})
export class IoTDevicesViewComponent implements OnInit {
  deviceId: number = undefined;
  create: Boolean = true;
  device: IoTDevice = new IoTDevice();
  valid: Boolean = true;
  constructor(
    private IoTDeviceService: IoTDeviceService,
    private snackbar: MatSnackBar,
    private router: Router,
    private route: ActivatedRoute,
    private location: Location
  ) {}

  ngOnInit(): void {
    if (this.route.snapshot.paramMap.has('id')) {
      this.deviceId = Number(this.route.snapshot.paramMap.get('id'));
      this.create = false;
    }
    if (this.deviceId != undefined) {
      this.IoTDeviceService
        .getIoTDevice(this.deviceId)
        .subscribe(
          (data) => {
            this.device = <IoTDevice>data;
          }, //changed
          (err) => {
            this.valid = false;
            this.snackbar.open('Error IoT Device not found', '', {
              duration: 3000,
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

  onSubmit(iot_device: JSON) {
    if (this.deviceId != undefined) {
      this.IoTDeviceService
        .editIoTDevice(this.deviceId, iot_device)
        .subscribe(
          (data) => {}, //changed
          (err) => {
            this.snackbar.open(
              'Error updating the IoT Device: ' + err.error,
              '',
              {
                duration: 3000,
              }
            );
          },
          () => {
            this.router.navigateByUrl('/devices');
            this.snackbar.open('IoT Device updated ', '', {
              duration: 3000,
            });
          }
        );
    } else {
      this.IoTDeviceService.createIoTDevice(iot_device).subscribe(
        (data) => {}, //changed
        (err) => {
          this.snackbar.open(
            'Error creating the IoT Device: ' + err.error,
            '',
            {
              duration: 3000,
            }
          );
        },
        () => {
          this.router.navigateByUrl('/devices');
          this.snackbar.open('IoT Device created ', '', {
            duration: 3000,
          });
        }
      );
    }
  }
}
