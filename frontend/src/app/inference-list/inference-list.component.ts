import { Component, OnInit } from '@angular/core';
import {InferenceService} from '../services/inference.service'
import { MatTableDataSource } from '@angular/material/table';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component';
import { MatSnackBar } from '@angular/material/snack-bar';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-inference-list',
  templateUrl: './inference-list.component.html',
  styleUrls: ['./inference-list.component.css']
})
export class InferenceListComponent implements OnInit {

  displayedColumns = ['id',  'model_result', 'replicas', 'input_format', 'input_config', 'external_host',
  'input_topic', 'output_topic', 'output_upper', 'limit', 'time', 'status', 'manage'];

  inferences: JSON[];
  dataSource = new MatTableDataSource(this.inferences);

  constructor(private inferenceService: InferenceService,
    public dialog: MatDialog,
    private snackbar: MatSnackBar,
    private route: ActivatedRoute) { }

  ngOnInit(): void {

    this.inferenceService.getInferences().subscribe((data: JSON[]) => {
      this.inferences = data;
      this.dataSource.data = this.inferences;
    }, (err) => {
      this.snackbar.open('Error connecting with the server', '', {
        duration: 10000
      });
    });

  }
  applyFilter(value: string) {
    value = value.trim().toLowerCase();
    this.dataSource.filter = value;
  }

  confirmStopping(id: number){
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Inference '+id + ' running from Kubernetes'}
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.stopInference(id);
      }
    });
  }
  stopInference(id: number){
    this.inferenceService.stopInference(id).subscribe(
      (data) => {},  //changed
      (err)=>{
        this.snackbar.open('Error stopping the inference: '+err.error, '', {
          duration: 4000
        });
      },
      ()=>{
            this.snackbar.open('Inference stopped', '', {
            duration: 3000
          });
          window.location.reload();
        }
   );
  }
  confirmDeletion(id: number) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Inference '+id }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.delete(id);
      }
    });
  }

  delete(id: number) {
    this.inferenceService.deleteInference(id).subscribe(
      (data) => {},  //changed
      (err)=>{
        this.snackbar.open('Error deleting the inference: '+err.error, '', {
          duration: 4000
        });
      },
      ()=>{
            this.snackbar.open('Inference deleted', '', {
            duration: 3000
          });
          this.deleteRowDataTable(id);
        }
   );
  }

  deleteRowDataTable (id: number) {
    const itemIndex = this.dataSource.data.findIndex(obj => obj['id'] === id);
    console.log(itemIndex);
    this.dataSource.data.splice(itemIndex, 1);
    this.dataSource._updateChangeSubscription(); // <-- Refresh the datasource
  }

}
