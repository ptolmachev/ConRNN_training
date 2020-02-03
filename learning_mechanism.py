import numpy as np
# import autograd.numpy as np
# from autograd import elementwise_grad as egrad
from collections import deque
from copy import deepcopy
from recurrent_net import CRNN
from matplotlib import pyplot as plt

from Error_function import *



class LearningMechanism():
    def __init__(self, RNN, params):
        self.RNN = RNN
        self.lr = params['lr']
        self.horizon = params['horizon']
        self.V_buffer = deque(maxlen=self.horizon + 1)
        self.u_buffer = deque(maxlen=self.horizon + 1)
        self.V_buffer.append(deepcopy(self.RNN.V))
        self.u_buffer.append(deepcopy(self.RNN.u))

        # #for gradient checking#####################################
        self.p_buffer = deque(maxlen=self.horizon + 1)
        self.q_buffer = deque(maxlen=self.horizon + 1)
        self.r_buffer = deque(maxlen=self.horizon + 1)
        self.l_buffer = deque(maxlen=self.horizon + 1)
        self.p = np.zeros((self.RNN.N, self.RNN.N, self.RNN.N), dtype = np.float64)
        self.q = np.zeros((self.RNN.N, self.RNN.N, self.RNN.N), dtype = np.float64)
        self.r = np.zeros((self.RNN.N, self.RNN.N), dtype = np.float64)
        self.l = np.zeros((self.RNN.N, self.RNN.N), dtype = np.float64)
        self.p_buffer.append(deepcopy(self.p))
        self.q_buffer.append(deepcopy(self.q))
        self.r_buffer.append(deepcopy(self.r))
        self.l_buffer.append(deepcopy(self.l))
        # #############################################################
        self.target_history = deque(maxlen=self.RNN.history_len)

    #     #############################################################
    def rhs_p(self):
        rhs_p = + np.einsum('ij,k->jki', np.eye(self.RNN.N), self.RNN.fr_fun(self.RNN.V)) \
                + np.einsum('ij,i,ikl->jkl', self.RNN.W, self.RNN.fr_fun_der(self.RNN.V), self.p) \
                - self.q
        return rhs_p

    def rhs_q(self):
        rhs_q = self.RNN.alpha * (self.RNN.beta * self.p - self.q)
        return rhs_q

    def rhs_r(self):
        rhs_r = np.einsum('ij,i,ik->jk', self.RNN.W, self.RNN.fr_fun_der(self.RNN.V), self.r) + np.eye(self.RNN.N) - self.l
        return rhs_r

    def rhs_l(self):
        rhs_l = self.RNN.alpha * (self.RNN.beta * self.r - self.l)
        return rhs_l

    def get_aux_variables(self):
        p_next = self.p + self.RNN.dt * (self.rhs_p())
        q_next = self.q + self.RNN.dt * (self.rhs_q())
        r_next = self.r + self.RNN.dt * (self.rhs_r())
        l_next = self.l + self.RNN.dt * (self.rhs_l())
        return p_next, q_next, r_next, l_next
    #############################################################

    def set_targets(self, out_nrns, targets):
        self.output_nrns = out_nrns
        self.targets = targets

    def rnn_step(self):

        # #############################################################
        # update aux variables befire V and u because they depend on the un-updeted variables
        p_next, q_next, r_next, l_next = self.get_aux_variables()
        self.p = deepcopy(p_next)
        self.q = deepcopy(q_next)
        self.r = deepcopy(r_next)
        self.l = deepcopy(l_next)
        # save in the buffer
        self.p_buffer.append(deepcopy(self.p))
        self.q_buffer.append(deepcopy(self.q))
        self.r_buffer.append(deepcopy(self.r))
        self.l_buffer.append(deepcopy(self.l))
        # #############################################################

        self.RNN.run(1) #one time-step
        self.V_buffer.append(deepcopy(self.RNN.V))
        self.u_buffer.append(deepcopy(self.RNN.u))

    def run_learning(self, T_steps):
        pass

    def calculate_Wb_change(self, desired):
        pass

class BPTT(LearningMechanism):
    def __init__(self, RNN, params):
        super().__init__(RNN, params)

    def backprop(self, target):
        h = self.horizon
        N = self.RNN.N
        dt = self.RNN.dt
        W = self.RNN.W
        alpha = self.RNN.alpha
        beta = self.RNN.beta
        # except initial conditions
        V_array = np.array(self.V_buffer)[1:, :].T # N x h
        V_init = np.array(self.V_buffer)[0, :]
        target = target.T # N x h
        grad_W = np.zeros((N, N), dtype = np.float64)
        grad_b = np.zeros((N), dtype = np.float64)
        # for every time-layer (except for the zeroth)
        for p in np.arange(h)[::-1]:
            delta = np.zeros((N, p + 1), dtype = np.float64)  # dE / d v
            gamma = np.zeros((N, p + 1), dtype = np.float64)  # dE / d u
            e = np.zeros(N, dtype = np.float64)
            e[self.output_nrns] = 2 * (self.RNN.fr_fun(V_array[self.output_nrns, p]) - target[:, p])
            delta[:, -1] = self.RNN.fr_fun_der(V_array[:, p]) * e # delta on the last time step
            #TODO: there must be an error! 100% in deltas or indices
            for t in np.arange(p)[::-1]:
                grad_W += dt * deepcopy(self.RNN.fr_fun(V_array[:, t]).reshape(N, 1) @ delta[:, t + 1].reshape(1, N))
                grad_b += dt * deepcopy(delta[:, t + 1])
                delta_t = delta[:, t + 1] + dt * delta[:, t + 1]\
                          @ (W.T * self.RNN.fr_fun_der(V_array[:, t])) \
                          + dt * alpha * beta * gamma[:, t + 1]
                gamma_t = gamma[:, t + 1] - dt * (alpha * gamma[:, t + 1] + delta[:, t + 1])
                delta[:, t] = deepcopy(delta_t)
                gamma[:, t] = deepcopy(gamma_t)

            #add the last piece: the gradient of weights from initial conditions to the first output
            grad_W += dt * deepcopy(self.RNN.fr_fun(V_init).reshape(N, 1) @ delta[:, 0].reshape(1, N))
            grad_b += dt * deepcopy(delta[:, 0])
        return grad_W, grad_b

    def calculate_Wb_change(self, desired):
        #use internal information from the buffer to calculate gradients
        #calculate error term
        gradient_W, gradient_b = self.backprop(desired)
        dW = -self.lr * deepcopy(gradient_W)
        db = -self.lr * deepcopy(gradient_b)
        return dW, db

    def run_learning(self, T_steps):
        for i in range(T_steps):
            if (i != 0) and (i % self.horizon == 0): # and
                desired = self.targets[i - self.horizon:i, :]
                #calculate weights and biases update
                dW_1, db_1 = self.calculate_Wb_change(desired)

                #autograd
                V_init = deepcopy(np.array(self.V_buffer)[0, :])
                u_init = deepcopy(np.array(self.u_buffer)[0, :])
                W_b = deepcopy(np.vstack([self.RNN.W, self.RNN.b]))
                E = Error_function(W_b, V_init, u_init, desired, self.output_nrns, self.horizon)
                grad_W_fun = egrad(Error_function)
                dWb = - deepcopy(self.lr * grad_W_fun(W_b, V_init, u_init, desired, self.output_nrns, self.horizon))

                dW_2 = dWb[:self.RNN.N, :]
                db_2 = dWb[self.RNN.N, :]

                #############################################################
                # calculate gradients:
                #take the arrays withouth the initial condition
                V_out = np.array(self.V_buffer)[1:, self.output_nrns]  # (t, o)
                p_out = np.array(self.p_buffer)[1:, self.output_nrns, :, :]  # (t, o, i, j)
                r_out = np.array(self.r_buffer)[1:, self.output_nrns, :]  # (t, o)

                e = 2 * (self.RNN.fr_fun(V_out) - desired)
                dW_3 = - self.lr * np.einsum("ij,ijkl->kl", e * self.RNN.fr_fun_der(V_out), p_out)
                db_3 = - self.lr * np.einsum("ij,ijk->k", e * self.RNN.fr_fun_der(V_out), r_out)
                #############################################################

                # apply changes
                # enforce zero self coupling
                np.fill_diagonal(dW_1, 0)
                np.fill_diagonal(dW_2, 0)
                np.fill_diagonal(dW_3, 0)

                new_W = self.RNN.W + dW_3
                np.fill_diagonal(new_W, 0)
                self.RNN.W = deepcopy(new_W)
                self.RNN.b = deepcopy(self.RNN.b + db_3)

                # self.lr *= 0.9995
                # enforce current state to coincide with the target state
                # self.RNN.V[self.output_nrns] = deepcopy(self.RNN.inverse_fr_fun(self.targets[i, :]))

                # reset buffer
                self.V_buffer = deque(maxlen=self.horizon + 1)
                self.u_buffer = deque(maxlen=self.horizon + 1)

                self.V_buffer.append(deepcopy(self.RNN.V))
                self.u_buffer.append(deepcopy(self.RNN.u))

                # reset auxiliary buffer
                #############################################################
                self.p_buffer = deque(maxlen=self.horizon + 1)
                self.q_buffer = deque(maxlen=self.horizon + 1)
                self.r_buffer = deque(maxlen=self.horizon + 1)
                self.l_buffer = deque(maxlen=self.horizon + 1)
                self.p = np.zeros((self.RNN.N, self.RNN.N, self.RNN.N))
                self.q = np.zeros((self.RNN.N, self.RNN.N, self.RNN.N))
                self.r = np.zeros((self.RNN.N, self.RNN.N))
                self.l = np.zeros((self.RNN.N, self.RNN.N))
                self.p_buffer.append(deepcopy(self.p))
                self.q_buffer.append(deepcopy(self.q))
                self.r_buffer.append(deepcopy(self.r))
                self.l_buffer.append(deepcopy(self.l))

            self.rnn_step()
            self.target_history.append(deepcopy(self.targets[i, :]))

    def visualise(self):
        V_array = np.array(self.RNN.V_history).T
        target_array = np.array(self.target_history).T
        t_array = np.array(self.RNN.t_range)
        fig, axes = plt.subplots(self.RNN.N, 1, figsize=(20, 10))
        if type(axes) != np.ndarray: axes = [axes]
        k = 0
        for i in range(len(axes)):
            if i == 0: axes[i].set_title('Firing Rates')

            if i in self.output_nrns:
                axes[i].plot(t_array, target_array[k], 'r', linewidth=2, alpha=0.5)
                k = k + 1

            axes[i].plot(t_array, self.RNN.fr_fun(V_array[i]), 'k', linewidth=2, alpha=0.9)
            axes[i].set_ylim([-0.1, 1.0])
            # axes[i].set_yticks([])
            # axes[i].set_yticklabels([])
            if i != len(axes) - 1:
                axes[i].set_xticks([])
                axes[i].set_xticklabels([])
            axes[i].set_xlabel('t, ms')
        plt.subplots_adjust(wspace=0.01, hspace=0)
        plt.show()
        return None

if __name__ == '__main__':
    N = 5
    dt = 0.2
    T_steps = 100000
    save_every = 1
    record = True

    params = dict()
    params['alpha'] = 0.004
    params['beta'] = 0.005
    params["V_half"] = 0.0
    params["slope"] = 50
    V_init = -50 + 100 * np.random.rand(N)
    u_init = 0.02 * np.random.rand(N) - 0.01
    weights = 1 * np.random.rand(N, N) - 0.67
    biases = 0.1 + 0.1 * np.random.rand(N)
    rnn = CRNN(N, dt, params, V_init, u_init, weights, biases, record=record, save_every=save_every)

    params_lm = dict()
    params_lm['lr'] = 7e-3
    params_lm['horizon'] = 100

    lm = BPTT(RNN=rnn, params=params_lm)
    out_nrns = [0, 1]
    t_range = np.arange(T_steps + 2 * params_lm['horizon'])
    targets = np.array([
                        # 0.25 * np.ones(len(t_range)),
                         # 0.75 * np.ones(len(t_range))
                        rnn.fr_fun(-30 + 150 * np.sin(np.pi / 800 * t_range) + 100 * np.cos(np.pi / 1200 * t_range)),
                        rnn.fr_fun(-30 + 150 * np.sin(np.pi / 900 * t_range + np.pi))
                        ]).T
    lm.set_targets(out_nrns, targets)
    lm.run_learning(T_steps)
    lm.visualise()

    rnn.reset_history()
    rnn.run(T_steps=25000)
    rnn.visualise_fr()

