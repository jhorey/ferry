#include <mpi.h>

int main(int argc, char **argv)
{
  int numprocs, rank, namelen;
  char proc_name[MPI_MAX_PROCESSOR_NAME];

  MPI_Init(&argc, &argv);
  MPI_Comm_size(MPI_COMM_WORLD, &numprocs);
  MPI_Comm_rank(MPI_COMM_WORLD, &rank);
  MPI_Get_processor_name(proc_name, &namelen);

  if(rank == 0) {
    std::cout << "Processor name: " << proc_name << "\n";
    std::cout << "master (" << rank << "/" << numprocs << ")\n";
  }
  else {
    std::cout << "slave (" << rank << "/" << numprocs << ")\n";
  }

  MPI_Finalize();
}
