import { async, ComponentFixture, TestBed } from '@angular/core/testing';

import { InferenceIoTViewComponent } from './inference-iot-view.component';

describe('InferenceViewComponent', () => {
  let component: InferenceIoTViewComponent;
  let fixture: ComponentFixture<InferenceIoTViewComponent>;

  beforeEach(async(() => {
    TestBed.configureTestingModule({
      declarations: [ InferenceIoTViewComponent ]
    })
    .compileComponents();
  }));

  beforeEach(() => {
    fixture = TestBed.createComponent(InferenceIoTViewComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
