import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { DatasourceListComponent } from './datasource-list.component';

describe('DatasourceListComponent', () => {
  let component: DatasourceListComponent;
  let fixture: ComponentFixture<DatasourceListComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ DatasourceListComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(DatasourceListComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
