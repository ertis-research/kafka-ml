import { Component, OnInit } from '@angular/core';
import { DatasourceService } from '../services/datasource.service';
import { MatTableDataSource } from '@angular/material/table';
import { MatDialog } from '@angular/material/dialog';
import {MatSnackBar} from '@angular/material/snack-bar';
import {DatasourceDialogComponent} from '../datasource-dialog/datasource-dialog.component'

@Component({
  selector: 'app-datasource-list',
  templateUrl: './datasource-list.component.html',
  styleUrls: ['./datasource-list.component.css']
})
export class DatasourceListComponent implements OnInit {

  displayedColumns = ['description', 'deployment', 'input_format', 'input_config', 'topic',
                      'validation_rate', 'test_rate', 'total_msg','time','deploy'];
  datasources : JSON[];
  dataSource = new MatTableDataSource(this.datasources);
  
  constructor(private datasourceService: DatasourceService,
              private datasourceDialog: DatasourceDialogComponent,
         public dialog: MatDialog,
         private snackbar: MatSnackBar) { }
         

  ngOnInit(): void {  

    this.datasourceService.getDatasources().subscribe((data: JSON[])=>{
     this.datasources=data;
     this.dataSource.data=this.datasources;
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

  confirm(value: JSON) {
    const dialogRef = this.dialog.open(DatasourceDialogComponent, {
      width: '400px',
    });

    dialogRef.afterClosed().subscribe(result => {
        if(result!=undefined){
          var data = JSON.parse(JSON.stringify(value))
          data['deployment']=result.toString()
          this.datasourceService.deployDatasource(data).subscribe((data: JSON)=>{
            this.snackbar.open('Datasource sent to Kafka. Refresh the page in a while to see it', '', {
              duration: 3000,
            });
           },(err)=>{
             console.log(err)
             this.snackbar.open('Error sending the datasource: '+err.error, '', {
               duration: 3000,
             });
           });
          
        }
    });
  }


}
