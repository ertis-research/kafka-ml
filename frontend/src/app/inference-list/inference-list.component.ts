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

  displayedColumns = ['id', 'model_result', 'input_format', 'input_config', 
  'input_topic', 'output_topic', 'time', 'status', 'stop', 'delete'];

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

  stopInference(id: number){
      // TODO
  }
  confirm(id: number){
     // TODO
  }

}
