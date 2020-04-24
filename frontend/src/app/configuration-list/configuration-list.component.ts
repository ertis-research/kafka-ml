import { Component } from '@angular/core';
import { ConfigurationService } from '../services/configuration.service';
import { MatDialog } from '@angular/material/dialog';
import { ConfirmDialogComponent } from '../confirm-dialog/confirm-dialog.component';
import {MatSnackBar} from '@angular/material/snack-bar';

@Component({
  selector: 'app-configuration-list',
  templateUrl: './configuration-list.component.html',
  styleUrls: ['./configuration-list.component.css']
})
export class ConfigurationListComponent {
  configurations = null;
  modelDisplayedColumns = ['id', 'name'];
  filtered_data: string = '';

  constructor(private configurationService: ConfigurationService, 
              public dialog: MatDialog,
              private snackbar: MatSnackBar) { }

  ngOnInit(): void {  

    this.configurationService.getConfigurations().subscribe((data: JSON[])=>{
          this.configurations=data;
    },
      (err)=>{
        this.snackbar.open('Error connecting with the server', '', {
            duration: 3000
        });
      });

  }

  confirm(id: number) {
    const dialogRef = this.dialog.open(ConfirmDialogComponent, {
      width: '300px',
      data: { title: 'Configuration '+id }
    });

    dialogRef.afterClosed().subscribe(result => {
      if (result) {
        this.delete(id);
      }
    });
  }

  delete(id: number) {
    this.configurationService.deleteConfiguration(id).subscribe(
      ()=>{
        this.snackbar.open('Configuration deleted', '', {
        duration: 3000
      });
      this.updateData(id);
    },(err)=>{
        this.snackbar.open('Error deleting the configuration: '+err.error, '', {
          duration: 4000
        });
      },
      
   );
  }

  updateData (id: number) {
    const itemIndex = this.configurations.findIndex(obj => obj['id'] === id);
    this.configurations.splice(itemIndex, 1);
  }

  applyFilter(value: string) {
    // TODO: apply filter
  }
  
}
