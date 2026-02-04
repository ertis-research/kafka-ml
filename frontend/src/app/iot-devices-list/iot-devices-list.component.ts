import { Component, OnInit } from '@angular/core';
import { IoTDeviceService } from '../services/iot-devices.service';
import { MatTableDataSource } from '@angular/material/table';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component';
import { MatSnackBar } from '@angular/material/snack-bar';
import { IoTDevice } from '../shared/iotdevice.model';

@Component({
  selector: 'app-iot-devices-list',
  templateUrl: './iot-devices-list.component.html',
  styleUrls: ['./iot-devices-list.component.css'],
  providers: [IoTDeviceService],
})
export class IoTDevicesListComponent implements OnInit {
  displayedColumns = [
    'id',
    'friendly_name',
    'broker',
    'backlog',
    'status',
    'edit',
    'delete',
  ];


  devices: JSON[];
  dataSource = new MatTableDataSource(this.devices);

  constructor(
    private iotDeviceService: IoTDeviceService,
    public dialog: MatDialog,
    private snackbar: MatSnackBar
  ) {}

  ngOnInit(): void {
    
    this.iotDeviceService.getIoTDevices().subscribe(
      (data: JSON[]) => {
        this.devices = data;
        this.dataSource.data = this.devices;
      },
      (err) => {
        this.snackbar.open('Error connecting with the server', ''),
          {
            duration: 3000,
          };
      }
    );
  }

  applyFilter(value: string) {
    value = value.trim().toLowerCase();
    this.dataSource.filter = value;
  }

  deleteDialog(id: number, token: string) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Device ' + token },
    });

    dialogRef.afterClosed().subscribe((result) => {
      if (result) {
        this.delete(id);
      }
    });
  }

  delete(id: number) {
    this.iotDeviceService.deleteIoTDevice(id).subscribe(
      (data) => {}, //changed
      (err) => {
        this.snackbar.open('Error deleting the device: ' + err.error, '', {
          duration: 4000,
        });
      },
      () => {
        this.snackbar.open('Model deleted', '', {
          duration: 3000,
        });
        this.deleteRowDataTable(id);
      }
    );
  }

  deleteRowDataTable(id: number) {
    const itemIndex = this.dataSource.data.findIndex((obj) => obj['id'] === id);
    console.log(itemIndex);
    this.dataSource.data.splice(itemIndex, 1);
    this.dataSource._updateChangeSubscription(); // <-- Refresh the datasource
  }

  copyToClipboard(text: string) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(text).then(
        () => {
          this.snackbar.open('Copied to clipboard', '', { duration: 3000 });
        },
        (err) => {
          this.snackbar.open('Error copying to clipboard: ' + err, '', { duration: 4000 });
        }
      );
    } else {
      // Fallback para navegadores antiguos
      const textarea = document.createElement('textarea');
      textarea.value = text;
      textarea.style.position = 'fixed';  // Evita que se haga scroll
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
  
      try {
        const successful = document.execCommand('copy');
        const msg = successful ? 'Copied to clipboard' : 'Failed to copy';
        this.snackbar.open(msg, '', { duration: 3000 });
      } catch (err) {
        this.snackbar.open('Error copying to clipboard', '', { duration: 4000 });
      }
  
      document.body.removeChild(textarea);
    }
  }  

  getName(obj: IoTDevice): string {
    if (obj) {
      return obj.friendly_name;
    }
  }
}
