import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { PlotViewComponent } from './plot-view.component';

describe('PlotViewComponent', () => {
  let component: PlotViewComponent;
  let fixture: ComponentFixture<PlotViewComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ PlotViewComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(PlotViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
