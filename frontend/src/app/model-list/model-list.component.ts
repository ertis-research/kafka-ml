import { Component, OnInit } from '@angular/core';
import { ModelService } from '../services/model.service';
import { MatTableDataSource } from '@angular/material/table';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component';
import {MatSnackBar} from '@angular/material/snack-bar';
import { MLModel } from '../shared/ml.model';

@Component({
  selector: 'app-model-list',
  templateUrl: './model-list.component.html',
  styleUrls: ['./model-list.component.css'],
  providers:  [ ModelService ]
})
export class ModelListComponent implements OnInit {

  displayedColumns = ['id', 'name', 'description', 'imports', 'code', 'distributed', 'father', 'view', 'delete'];
  models : JSON[];
  dataSource = new MatTableDataSource(this.models);
  
  constructor(private modelService: ModelService,
         public dialog: MatDialog,
         private snackbar: MatSnackBar) { }

  ngOnInit(): void {  

    this.modelService.getModels().subscribe((data: JSON[])=>{
     this.models=data;
     this.dataSource.data=this.models;
    },(err)=>{
      this.snackbar.open('Error connecting with the server', ''), {
        duration: 3000
      }
    });
  }

  applyFilter(value: string) {
    value = value.trim().toLowerCase();
    this.dataSource.filter = value;
  }

  confirm(id: number) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Model '+id }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.delete(id);
      }
    });
  }

  delete(id: number) {
    this.modelService.deleteModel(id).subscribe(
      (data) => {},  //changed
      (err)=>{
        this.snackbar.open('Error deleting the model: '+err.error, '', {
          duration: 4000
        });
      },
      ()=>{
            this.snackbar.open('Model deleted', '', {
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

  getName(obj: MLModel): string {
    if (obj) {
      return obj.name;
    }
  }
}
